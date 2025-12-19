from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QTextEdit, QVBoxLayout, QHBoxLayout, QFrame, QTableWidget,
    QTableWidgetItem
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap, QFont
import sys
import cv2
import time
import random
from ultralytics import YOLO


# ============================================================
# UI 卡片樣式
# ============================================================
class CardFrame(QFrame):
    def __init__(self, title=""):
        super().__init__()
        self.setStyleSheet("""
            QFrame {
                background-color: #F7F9FC;
                border: 2px solid #D0D7E1;
                border-radius: 12px;
            }
            QLabel {
                font-size: 22px;
                font-weight: bold;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        if title:
            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("color:#2C3E50;font-size:24px;font-weight:bold;")
            layout.addWidget(title_label)

        self.content = QVBoxLayout()
        layout.addLayout(self.content)



# ============================================================
# 主 GUI
# ============================================================
class BMI_GUI(QMainWindow):
    def __init__(self):
        super().__init__()

        # 偵測狀態參數
        self.last_detect_time = 0
        self.detect_paused = False
        self.face_seen_time = None
        self.ready_to_detect = False

        self.setWindowTitle("BMI 偵測系統")
        self.resize(1700, 900)

        # 載入 YOLO 模型
        self.model = YOLO(
            r"C:/Users/add77/Desktop/yolo/ultralytics-8.3.20/runs/train/exp7/weights/best.pt"
        )

        # 主 Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # ========================================================
        # 左側 控制面板
        # ========================================================
        left_panel = QFrame()
        left_panel.setFixedWidth(260)
        left_panel.setStyleSheet("""
            QFrame { background-color: #ECF1F7; border-right: 2px solid #D0D7E1; }
            QPushButton {
                background-color: #4A90E2; color: white; font-size: 22px;
                padding: 14px; border-radius: 10px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)

        self.btn_start = QPushButton("📷 開始偵測")
        self.btn_pause = QPushButton("⏸ 停止偵測")
        left_layout.addWidget(self.btn_start)
        left_layout.addWidget(self.btn_pause)

        log_title = QLabel("日誌 Log")
        log_title.setFont(QFont("", 18, QFont.Bold))
        left_layout.addWidget(log_title)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        left_layout.addWidget(self.log_box)

        # ========================================================
        # 中間 相機畫面
        # ========================================================
        center_layout = QVBoxLayout()
        top_center = QHBoxLayout()

        self.camera_card = CardFrame("相機畫面")
        self.cam_preview = QLabel("等待相機…")
        self.cam_preview.setFixedSize(500, 500)
        self.cam_preview.setAlignment(Qt.AlignCenter)
        self.cam_preview.setStyleSheet("""
            QLabel {
                background:black;border:2px solid #4A90E2;
                border-radius:10px;color:white;font-size:22px;
            }
        """)
        self.camera_card.content.addWidget(self.cam_preview)
        top_center.addWidget(self.camera_card)

        # ========================================================
        # 右側：偵測結果 + 菜單 + 健康分析 + 歷史紀錄
        # ========================================================
        right_panel = CardFrame("偵測結果")

        # 分類結果
        self.result_label = QLabel("BMI 分類：尚未偵測")
        self.result_label.setStyleSheet("font-size:22px;")
        right_panel.content.addWidget(self.result_label)

        # 建議菜單
        self.meal_label = QLabel("🍱 建議菜單：尚未提供")
        self.meal_label.setStyleSheet("font-size:20px;color:#333;")
        right_panel.content.addWidget(self.meal_label)

        # 健康分析
        self.health_label = QLabel("🔥 健康分析：尚未提供")
        self.health_label.setStyleSheet("font-size:20px;color:#555;")
        right_panel.content.addWidget(self.health_label)

        # ---- 歷史紀錄表格（重要）----
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(
            ["時間", "分類", "BMI", "信心度", "餐點", "健康分析"]
        )
        self.history_table.setFixedHeight(260)

        # 欄位寬度
        self.history_table.setColumnWidth(0, 110)
        self.history_table.setColumnWidth(1, 70)
        self.history_table.setColumnWidth(2, 60)
        self.history_table.setColumnWidth(3, 80)
        self.history_table.setColumnWidth(4, 260)
        self.history_table.setColumnWidth(5, 260)

        self.history_table.setWordWrap(True)
        self.history_table.resizeRowsToContents()

        right_panel.content.addWidget(self.history_table)

        top_center.addWidget(right_panel)
        center_layout.addLayout(top_center)

        main_layout.addWidget(left_panel)
        main_layout.addLayout(center_layout)

        # Timer
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_frame)

        self.btn_start.clicked.connect(self.start_camera)
        self.btn_pause.clicked.connect(self.stop_camera)



    # ============================================================
    # 菜單 & 健康分析
    # ============================================================
    def get_random_meal(self, label):

        thin_meals = [
            ("鮭魚排 120g", 240, 23, 14, 2),
            ("糙米飯 150g", 210, 4, 2, 45),
            ("炒青花菜 100g", 55, 4, 1, 8),
            ("豆腐味噌湯", 80, 6, 4, 5)
        ]

        obesity_meals = [
            ("清蒸鱈魚 100g", 115, 20, 3, 0),
            ("水煮花椰菜 150g", 70, 5, 1, 12),
            ("山藥小碗", 90, 2, 0, 21),
            ("少量白飯 80g", 110, 2, 0, 25)
        ]

        meals = thin_meals if label == "thin" else obesity_meals
        chosen = random.sample(meals, 3)

        # 營養總合
        total_cal = sum(m[1] for m in chosen)
        total_prot = sum(m[2] for m in chosen)
        total_fat = sum(m[3] for m in chosen)
        total_carb = sum(m[4] for m in chosen)

        meal_text = "🍱 今日推薦菜單：\n" + "\n".join([m[0] for m in chosen])
        health_text = (
            f"🔥 健康分析：\n"
            f"熱量：{total_cal} kcal\n"
            f"蛋白質：{total_prot} g\n"
            f"脂肪：{total_fat} g\n"
            f"碳水：{total_carb} g"
        )

        # 用於歷史表格的單行版本
        meal_single_line = ", ".join([m[0] for m in chosen])
        health_single_line = (
            f"{total_cal} kcal, 蛋白質:{total_prot}g, 脂肪:{total_fat}g, 碳水:{total_carb}g"
        )

        return meal_text, health_text, meal_single_line, health_single_line



    # ============================================================
    # 歷史紀錄寫入（包含菜單 + 健康分析）
    # ============================================================
    def add_history(self, label, bmi, conf, meal_text, health_text):
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)

        timestamp = time.strftime("%H:%M:%S")

        self.history_table.setItem(row, 0, QTableWidgetItem(timestamp))
        self.history_table.setItem(row, 1, QTableWidgetItem(label))
        self.history_table.setItem(row, 2, QTableWidgetItem(str(bmi)))
        self.history_table.setItem(row, 3, QTableWidgetItem(f"{conf:.2f}"))
        self.history_table.setItem(row, 4, QTableWidgetItem(meal_text))
        self.history_table.setItem(row, 5, QTableWidgetItem(health_text))
        # 讓高度配合多行文字
        self.history_table.resizeRowToContents(row)

        if row >= 30:
            self.history_table.removeRow(0)



    # ============================================================
    # 啟動相機
    # ============================================================
    def start_camera(self):
        self.detect_paused = False
        self.face_seen_time = None
        self.ready_to_detect = False

        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.timer.start(30)



    # ============================================================
    # YOLO 偵測流程
    # ============================================================
    def process_frame(self):
        if not self.cap:
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        if self.detect_paused:
            self._update_preview(self.paused_frame)
            return

        results = self.model.predict(frame, conf=0.25, verbose=False)[0]

        # 判斷是否穩定 2 秒
        if results.boxes:
            if self.face_seen_time is None:
                self.face_seen_time = time.time()
            elif time.time() - self.face_seen_time >= 2:
                if not self.ready_to_detect:
                    self.ready_to_detect = True
        else:
            self.face_seen_time = None
            self.ready_to_detect = False

        # ---- 偵測成功（每2秒一次）----
        if self.ready_to_detect and time.time() - self.last_detect_time >= 2:
            self.last_detect_time = time.time()

            b = results.boxes[0]
            x1, y1, x2, y2 = map(int, b.xyxy[0])

            cls = int(b.cls)
            label = results.names[cls]
            conf = float(b.conf)

            # 隨機 BMI
            bmi_value = (
                random.uniform(18.5, 24)
                if label == "thin" else
                random.uniform(24, 27)
            )
            bmi_value = round(bmi_value, 1)

            # 畫框
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)
            cv2.putText(frame, f"{label} BMI:{bmi_value}",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0,255,0), 2)

            # 信心度條
            self.update_confidence_bar(label, conf)

            # 產生菜單 + 健康分析
            menu_text, health_text, menu_single, health_single = self.get_random_meal(label)

            self.meal_label.setText(menu_text)
            self.health_label.setText(health_text)

            # ---- 寫入歷史紀錄 ----
            self.add_history(label, bmi_value, conf, menu_single, health_single)

            # 凍結畫面
            self.paused_frame = frame.copy()
            self.detect_paused = True
            self._update_preview(self.paused_frame)
            return

        self._update_preview(frame)



    # ============================================================
    # 信心度條
    # ============================================================
    def update_confidence_bar(self, label, conf):
        thin_score = conf if label == "thin" else 1 - conf
        obese_score = conf if label == "obesity" else 1 - conf
        bar = lambda v: "█" * int(v * 20) + "░" * (20 - int(v * 20))

        text = (
            f"BMI 分類：{label}\n\n"
            f"thin : {thin_score:.2f} {bar(thin_score)}\n"
            f"obesity : {obese_score:.2f} {bar(obese_score)}"
        )
        self.result_label.setText(text)



    # ============================================================
    # 更新相機畫面
    # ============================================================
    def _update_preview(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.cam_preview.setPixmap(pixmap)



    # ============================================================
    # 停止相機
    # ============================================================
    def stop_camera(self):
        if self.cap:
            self.cap.release()
            self.cap = None

        self.timer.stop()
        self.cam_preview.setText("相機已停止")
        self.result_label.setText("BMI 分類：尚未偵測")
        self.meal_label.setText("🍱 建議菜單：尚未提供")
        self.health_label.setText("🔥 健康分析：尚未提供")



# ============================================================
# 主程式入口
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BMI_GUI()
    window.show()
    sys.exit(app.exec())

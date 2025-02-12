import sys
import ctypes
from threading import Thread
from queue import Queue

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QScrollArea,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QMessageBox, QLineEdit
)
from PyQt5.QtGui import QPixmap, QImage, QIntValidator, QIcon
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtWidgets import QMessageBox, QPushButton, QLabel, QDialog, QVBoxLayout

import fitz  # PyMuPDF -> pip install pymupdf

import pystray
from pystray import MenuItem as item
from PIL import Image as PILImage
import os

from Crypto.Util.Padding import unpad # pip install pycryptodome
from Crypto.Cipher import AES # pip install pycryptodome
from tkinter import messagebox
import base64
import requests
import urllib.parse

# =============== Windows 캡처 방지 관련 함수 ===============
WDA_NONE               = 0x00000000
WDA_MONITOR            = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011  # decimal 17

# ======================= 키 받아야 함 ===========================
global download_url, key, iv # 복호화 관련

# download_url = None
down_file_path = r'C:\Windows\Temp\static_pdf.pdf'

key_get_url = "http://3.35.84.46:8080/get-key"
file_get_url = "http://3.35.84.46:8080/generate-presigned-url"

download_url = None
iv = None
key = None

user_id = None
book_id = None

# ----------------------------------------------------------

def set_display_affinity(hwnd, exclude=True):
    if sys.platform != 'win32':
        print("[!] Non-Windows platform: skipping SetWindowDisplayAffinity.")
        return

    affinity_flag = WDA_EXCLUDEFROMCAPTURE if exclude else WDA_NONE
    result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, affinity_flag)
    if result == 0:
        err_code = ctypes.windll.kernel32.GetLastError()
        print(f"[!] Failed to set display affinity. Error code: {err_code}")
    else:
        print("[+] Display affinity set successfully.")

# =============== PDF 뷰어 ===============
class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EQST - eBook Viewer")
        self.view_mode = 1
        self.setMinimumSize(875, 650)
        self.resize(875, 650)
        # 메인 레이아웃
        main_widget = QWidget()
        self.main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # 스크롤 가능 영역
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.main_layout.addWidget(self.scroll_area)

        # 스크롤 내부 컨테이너 + 레이아웃
        self.scroll_container = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_container)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_container)

        self.setup_controls()
        self.resize(875, 650)
        QTimer.singleShot(100, self.open_pdf)

    def open_pdf(self):
        # 기존 페이지 이미지 모두 제거
        for i in reversed(range(self.scroll_layout.count())):
            widget_item = self.scroll_layout.itemAt(i)
            widget = widget_item.widget()
            if widget:
                widget.deleteLater()

        try:
            self.doc = fitz.open(down_file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"eBook 열람 실패: {e}")
            return

        self.total_pages = len(self.doc)  # 전체 페이지 개수 저장
        self.current_page = 0  # 첫 페이지 (0부터 시작)
        
        self.scale_factor = 0.67

        # UI 요소 업데이트 (최초 배율 & 페이지 정보)
        self.zoom_input.setText(f"{int(self.scale_factor * 100)}")  # 배율 업데이트
        self.page_label.setText(f"{self.current_page + 1} / {self.total_pages}")  # 페이지 정보 업데이트

        self.display_page()  # 첫 페이지 로드

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:  # Ctrl 키가 눌린 상태인지 확인
            delta = event.angleDelta().y() / 120  # 스크롤 방향 감지 (+1, -1)
            scale_step = 0.1
            self.adjust_scale(delta * scale_step)  # 배율 조정

    def set_view_mode(self, mode):
        self.view_mode = mode  # 보기 모드 변경 (1 or 2)
        self.display_page()  # 화면 업데이트

    def display_page(self):
        # 기존 페이지 제거
        for i in reversed(range(self.scroll_layout.count())):
            widget_item = self.scroll_layout.itemAt(i)
            widget = widget_item.widget()
            if widget:
                widget.deleteLater()

        # 2페이지 모드이고 현재 페이지가 마지막 페이지가 아닌 경우
        if self.view_mode == 2:
            if self.current_page < self.total_pages - 1:
                pages = [self.doc.load_page(self.current_page), 
                        self.doc.load_page(self.current_page + 1)]
            else:  # 마지막 페이지인 경우 한 페이지만 표시
                pages = [self.doc.load_page(self.current_page)]
        else:
            pages = [self.doc.load_page(self.current_page)]

        labels = []
        for page in pages:
            pix = page.get_pixmap(matrix=fitz.Matrix(self.scale_factor, self.scale_factor))
            mode = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, mode)
            pixmap = QPixmap.fromImage(qimg)

            label = QLabel()
            label.setPixmap(pixmap)
            labels.append(label)

        hbox = QHBoxLayout()
        hbox.setAlignment(Qt.AlignCenter)
        for label in labels:
            hbox.addWidget(label)

        container = QWidget()
        container.setLayout(hbox)
        self.scroll_layout.addWidget(container)
    
    def closeEvent(self, event):
        self.doc.close()
        self.doc = None
        self.delete_pdf_file()
        QApplication.quit()
        event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        hwnd = self.winId().__int__()
        set_display_affinity(hwnd, True)

    def delete_pdf_file(self):
        if os.path.exists(down_file_path):
            os.remove(down_file_path)

    def change_page(self, direction):
        if self.view_mode == 1:  # 1페이지 모드
            new_page = self.current_page + direction
            if 0 <= new_page < self.total_pages:
                self.current_page = new_page
                self.page_label.setText(f"{self.current_page + 1} / {self.total_pages}")
                self.display_page()
        else:  # 2페이지 모드
            new_page = self.current_page + (direction * 2)  # 2페이지씩 이동
            if direction > 0 and new_page >= self.total_pages:
                if self.current_page < self.total_pages - 1:  # 마지막 페이지가 남아있는 경우
                    self.current_page = self.total_pages - 1
            elif direction < 0 and new_page < 0:
                self.current_page = 0
            elif 0 <= new_page < self.total_pages:
                self.current_page = new_page
            
            self.page_label.setText(f"{self.current_page + 1} / {self.total_pages}")
            self.display_page()

    def adjust_scale(self, delta):
        new_scale = self.scale_factor + delta
        if 0.5 <= new_scale <= 3.0:  # 배율 제한 (50% ~ 300%)
            self.scale_factor = new_scale
            self.zoom_input.setText(f"{int(self.scale_factor * 100)}")  # 배율 입력 필드 업데이트
            self.display_page()  # 변경된 배율로 페이지 다시 표시

    def setup_controls(self):
        control_layout = QHBoxLayout()
        icon_path_sk = get_resource_path("img/sk_shieldus_butterfly_rgb_kr.png")
        icon_path_back = get_resource_path("img/back.png")
        icon_path_next = get_resource_path("img/next.png")
        icon_path_plus = get_resource_path("img/plus.png")
        icon_path_minus = get_resource_path("img/minus.png")
        icon_path_page_1 = get_resource_path("img/page_1.png")
        icon_path_page_2 = get_resource_path("img/page_2.png")
        
        self.setWindowIcon(QIcon(icon_path_sk))

        page_layout = QHBoxLayout()
        page_layout.setAlignment(Qt.AlignCenter)

        self.prev_page_btn = QPushButton()
        self.prev_page_btn.setIcon(QIcon(icon_path_back))
        self.prev_page_btn.setIconSize(QSize(50, 15))
        self.prev_page_btn.setFixedWidth(200)
        self.prev_page_btn.clicked.connect(lambda: self.change_page(-1))
        page_layout.addWidget(self.prev_page_btn)

        self.page_label = QLabel()
        self.page_label.setFixedWidth(80)
        self.page_label.setAlignment(Qt.AlignCenter)
        page_layout.addWidget(self.page_label)

        self.next_page_btn = QPushButton()
        self.next_page_btn.setIcon(QIcon(icon_path_next))
        self.next_page_btn.setIconSize(QSize(50, 15))
        self.next_page_btn.setFixedWidth(200)
        self.next_page_btn.clicked.connect(lambda: self.change_page(1))
        page_layout.addWidget(self.next_page_btn)

        zoom_layout = QHBoxLayout()
        zoom_layout.setAlignment(Qt.AlignRight)

        self.zoom_out_btn = QPushButton()
        self.zoom_out_btn.setIcon(QIcon(icon_path_minus))
        self.zoom_out_btn.setIconSize(QSize(10, 10))
        self.zoom_out_btn.setFixedWidth(30)
        self.zoom_out_btn.clicked.connect(lambda: self.adjust_scale(-0.1))
        zoom_layout.addWidget(self.zoom_out_btn)

        self.zoom_input = QLineEdit()
        self.zoom_input.setFixedWidth(30)
        self.zoom_input.setAlignment(Qt.AlignCenter)
        self.zoom_input.setValidator(QIntValidator(50, 300))
        self.zoom_input.returnPressed.connect(self.manual_scale_update)
        zoom_layout.addWidget(self.zoom_input)

        self.zoom_in_btn = QPushButton()
        self.zoom_in_btn.setIcon(QIcon(icon_path_plus))
        self.zoom_in_btn.setIconSize(QSize(10, 10))
        self.zoom_in_btn.setFixedWidth(30)
        self.zoom_in_btn.clicked.connect(lambda: self.adjust_scale(0.1))
        zoom_layout.addWidget(self.zoom_in_btn)

        mode_layout = QHBoxLayout()
        mode_layout.setAlignment(Qt.AlignCenter)

        self.one_page_btn = QPushButton()
        self.one_page_btn.setIcon(QIcon(icon_path_page_1))
        self.one_page_btn.setIconSize(QSize(15, 15))
        self.one_page_btn.setFixedWidth(30)
        self.one_page_btn.clicked.connect(lambda: self.set_view_mode(1))
        mode_layout.addWidget(self.one_page_btn)

        self.two_page_btn = QPushButton()
        self.two_page_btn.setIcon(QIcon(icon_path_page_2))
        self.two_page_btn.setIconSize(QSize(20, 15))
        self.two_page_btn.setFixedWidth(30)
        self.two_page_btn.clicked.connect(lambda: self.set_view_mode(2))
        mode_layout.addWidget(self.two_page_btn)

        # 전체 레이아웃 설정
        control_layout.addStretch(1)
        control_layout.addLayout(page_layout)
        control_layout.addStretch(1)
        control_layout.addLayout(mode_layout)
        control_layout.addStretch(1)
        control_layout.addLayout(zoom_layout)
        
        self.main_layout.addLayout(control_layout)

    def manual_scale_update(self):
        try:
            new_scale = int(self.zoom_input.text()) / 100
            if 0.5 <= new_scale <= 3.0:
                self.scale_factor = new_scale
                self.display_page()
            else:
                self.zoom_input.setText(f"{int(self.scale_factor * 100)}")
        except ValueError:
            self.zoom_input.setText(f"{int(self.scale_factor * 100)}")

# =============== 메인 스레드에서 실행될 함수들 ===============
def invoke_in_main_thread(func):
    main_thread_queue.put(func)

def get_resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return relative_path

def process_main_thread_queue():
    while not main_thread_queue.empty():
        func = main_thread_queue.get_nowait()
        func()

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def show_version_main():
    global window
    parent = window if (window and window.isVisible()) else None

    msg_box = QDialog(parent)
    msg_box.setWindowTitle("Version")
    icon_path_sk = get_resource_path("img/sk_shieldus_butterfly_rgb_kr.png")
    msg_box.setWindowIcon(QIcon(icon_path_sk))

    icon_label = QLabel()
    icon_path_EQST = get_resource_path("img/EQST.png")
    pixmap = QPixmap(icon_path_EQST).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    icon_label.setPixmap(pixmap)

    text_label = QLabel("eBook Viewer: 1.0.0")

    ok_button = QPushButton("OK")
    ok_button.clicked.connect(msg_box.accept)

    content_layout = QHBoxLayout()
    content_layout.addWidget(icon_label)
    content_layout.addWidget(text_label)

    layout = QVBoxLayout()
    layout.addLayout(content_layout)
    layout.addWidget(ok_button, alignment=Qt.AlignCenter)
    msg_box.setLayout(layout)

    msg_box.setFixedSize(210, 100)

    msg_box.exec_()

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def show_user_main():
    global window, user_id
    parent = window if (window and window.isVisible()) else None

    msg_box = QDialog(parent)
    msg_box.setWindowTitle("User Information")
    icon_path_sk = get_resource_path("img/sk_shieldus_butterfly_rgb_kr.png")
    msg_box.setWindowIcon(QIcon(icon_path_sk))

    icon_label = QLabel()
    icon_path_EQST = get_resource_path("img/EQST.png")
    pixmap = QPixmap(icon_path_EQST).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    icon_label.setPixmap(pixmap)

    text_label = QLabel(f"사용자 ID: {user_id}")

    ok_button = QPushButton("OK")
    ok_button.clicked.connect(msg_box.accept)

    content_layout = QHBoxLayout()
    content_layout.addWidget(icon_label)
    content_layout.addWidget(text_label)

    layout = QVBoxLayout()
    layout.addLayout(content_layout)
    layout.addWidget(ok_button, alignment=Qt.AlignCenter)
    msg_box.setLayout(layout)

    text_width = text_label.sizeHint().width() + 20  # 텍스트 크기에 여백 추가
    icon_width = icon_label.sizeHint().width() + 20  # 아이콘 크기에 여백 추가

    min_width = max(180, text_width + icon_width)  # 최소 180px, 텍스트 및 아이콘 크기에 따라 조정

    msg_box.setMinimumWidth(min_width)
    msg_box.setFixedHeight(100)

    msg_box.exec_()

def open_viewer_main():
    global window
    if window is None:
        window = PDFViewer()
        window.resize(875, 650)
    window.show()
    window.raise_()
    window.activateWindow()

# =============== pystray 콜백 (별도 스레드) ===============
def action_option1(icon, item):
    invoke_in_main_thread(show_version_main)

def action_option2(icon, item):
    invoke_in_main_thread(show_user_main)

# def action_option3(icon, item): # 트레이 우클릭(오픈 뷰어어)
#     invoke_in_main_thread(open_viewer_main)

def exit_action(icon, item):
    icon.stop()
    invoke_in_main_thread(app.quit)

def setup_tray_icon():
    # 이미지 파일 경로 설정
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TRAY_ICON_PATH = os.path.join(BASE_DIR, "img/sk_shieldus_butterfly_rgb_kr.png")

    try:
        image = PILImage.open(TRAY_ICON_PATH)
    except Exception as e:
        print("[!] Tray icon image load failed:", e)
        image = PILImage.new("RGB", (64, 64), "gray")

    menu = (
        item('Version', action_option1),
        item('User', action_option2),
        item('Exit', exit_action)
    )
    icon = pystray.Icon("eBook Viewer", image, "eBook Viewer", menu)
    icon.run()

# =============== Agent 복호화 ===============
def get_key_file():
    global download_url, key, iv
    try:
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "user_id": f"{user_id}", "book_id": f"{book_id}"
        }
        file_response = requests.post(file_get_url, json=data, headers=headers, timeout=5)
        if file_response.ok:
            response_data_file = file_response.json()
            response_data_file = response_data_file.get("presigned_url", None)
            download_url = response_data_file
            
            kms_response_data = requests.get(key_get_url)
            kms_response_data = kms_response_data.json()
            kms_response_data_key = kms_response_data.get("aes_key")
            kms_response_data_iv = kms_response_data.get("aes_iv")
            key = kms_response_data_iv
            iv = kms_response_data_key
            return download_url, key, iv
    except Exception as e:
        messagebox.showerror("에러", f"링크 다운로드 실패")
        sys.exit(1)

def adjust_key_length(key):
    try:
        key_decode = base64.b64decode(key)
        key = key_decode.decode('UTF-8')
        key = key.encode()

        if len(key) > 16:
            return key[:16]
        elif len(key) < 16:
            padding = b'\0' * (16 - len(key))
            return key + padding
        else:
            return key
    except:
        messagebox.showerror("에러", f"Key값 오류")
        sys.exit(1)

def adjust_IV_length(IV):
    try:
        IV_decode = base64.b64decode(IV)
        IV = IV_decode.decode('UTF-8')
        IV = IV.encode()

        if len(IV) > 16:
            return IV[:16]
        elif len(IV) < 16:
            padding = b'\0' * (16 - len(IV))
            return IV + padding
        else:
            return IV
    except:
        messagebox.showerror("에러", f"IV값 오류")
        sys.exit(1)

def dec_file(input_file, key, iv):
    try:
        with open(input_file, 'rb') as f:
            ciphertext = f.read()

        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_data = unpad(cipher.decrypt(ciphertext), AES.block_size)

        with open(input_file[:input_file.rfind('.')]+".Pdf", 'wb') as f:
            f.write(decrypted_data)
    except:
        messagebox.showerror("에러", f"파일 여는 중 오류 발생")
        sys.exit(1)

def pdf_file_down(download_url, down_file_path):
    try:
        if download_url != None:
            with requests.get(download_url, stream=True) as response:
                response.raise_for_status()
                
                with open(down_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:  
                            f.write(chunk)
    except:
        messagebox.showerror("에러", f"파일 다운로드 중 오류 발생")
        sys.exit(1)

# =============== 메인 실행부 ===============
app = None
window = None

if __name__ == "__main__":
    from PyQt5.QtCore import QTimer
    icon_path = resource_path('img/sk_shieldus_butterfly_rgb_kr_ico.ico')
    # URI로 전달된 파라미터 값 추출
    if len(sys.argv) > 1:
        uri = sys.argv[1]
        parsed_uri = urllib.parse.urlparse(uri)
        params = urllib.parse.parse_qs(parsed_uri.query)
        print("Received parameters:", params)

        user_id = params.get("user_id", ["None"])[0]
        book_id = params.get("book_id", ["None"])[0]

    #Agent PDF 복호화
    get_key_file()
    pdf_file_down(download_url, down_file_path)
    if iv != None or key != None:
        key = adjust_key_length(key)
        iv = adjust_IV_length(iv)
        dec_file(down_file_path, key, iv)
    else:
        messagebox.showerror("에러", f"Key, IV, URL 값 없음")
        sys.exit(1)

    if download_url != None and key != None and iv != None:
        # Main thread-safe queue
        main_thread_queue = Queue()

        # QApplication 초기화
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        # 주기적으로 PyQt 이벤트 루프에서 큐 처리
        timer = QTimer()
        timer.timeout.connect(process_main_thread_queue)
        timer.start(50)  # 50ms 간격으로 큐 처리

        # 트레이 아이콘 실행
        tray_thread = Thread(target=setup_tray_icon, daemon=True)
        tray_thread.start()

        # 처음 창 띄우기
        window = PDFViewer()
        window.resize(800, 600)
        window.show()

        sys.exit(app.exec_())
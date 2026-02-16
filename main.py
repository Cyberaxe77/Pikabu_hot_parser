#!/usr/bin/env python3

import sys
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from PySide6.QtCore import QThread, Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QListWidget,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QMessageBox,
    QMenu,
    QSystemTrayIcon,
)


# 1. Создаем класс-рабочий
class ParserWorker(QThread):
    # Сигналы для передачи данных обратно в основное окно
    finished = Signal(list)  # Передаст список кортежей (заголовок, ссылка)
    error = Signal(str)  # Передаст текст ошибки

    def run(self):
        """Метод, который выполняется в отдельном потоке"""
        ua = UserAgent()
        headers = {"User-Agent": ua.random}
        url = "https://pikabu.ru/hot"

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            posts = soup.find_all("article", class_="story")

            data = []
            for post in posts:
                title_tag = post.find("h2", class_="story__title")
                link_tag = post.find("a", class_="story__title-link")
                if title_tag and link_tag:
                    title = title_tag.get_text(strip=True)
                    link = link_tag.get("href", "")
                    if isinstance(link, str) and not link.startswith("http"):
                        link = "https://pikabu.ru" + link
                    elif not isinstance(link, str):
                        continue
                    data.append((title, link))

            # Отправляем результат через сигнал
            self.finished.emit(data)
        except Exception as e:
            # Отправляем ошибку через сигнал
            self.error.emit(str(e))


class PikabuThreadApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Пикабушный парсер "Горячего"')
        self.resize(600, 400)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.itemDoubleClicked.connect(self.open_in_browser)

        self.btn_load = QPushButton('Загрузить "горячее"')
        self.btn_load.clicked.connect(self.start_loading)

        main_layout.addWidget(self.list_widget)
        main_layout.addWidget(self.btn_load)

        self.worker = None
        self.post_links = {}
        
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("applications-internet"))
        
        tray_menu = QMenu()
        show_action = QAction("Показать", self)
        show_action.triggered.connect(self.show)
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def start_loading(self):
        """Запуск потока"""
        try:
            if self.worker and self.worker.isRunning():
                return
        except RuntimeError:
            pass

        self.btn_load.setEnabled(False)  # Отключаем кнопку на время загрузки
        self.btn_load.setText("Загрузка...")
        self.list_widget.clear()
        self.post_links.clear()

        # Создаем и запускаем поток
        self.worker = ParserWorker()

        # Подключаем сигналы к методам обработки
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)

        # Важно: удаляем объект потока из памяти после завершения
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)

        self.worker.start()

    def on_finished(self, data):
        """Слот для успешного завершения"""
        if data:
            self.post_links.clear()
            for title, link in data:
                self.list_widget.addItem(title)
                self.post_links[title] = link
        else:
            self.list_widget.addItem("Ничего не найдено.")

        self.reset_button()

    def on_error(self, message):
        """Слот для обработки ошибок"""
        QMessageBox.critical(
            self,
            "Ошибка",
            "Не удалось загрузить данные. Проверьте подключение к интернету.",
        )
        self.reset_button()

    def reset_button(self):
        """Возвращаем кнопку в рабочее состояние"""
        self.btn_load.setEnabled(True)
        self.btn_load.setText('Загрузить "горячее"')

    def open_in_browser(self, item):
        """Открыть ссылку в браузере"""
        title = item.text()
        if title in self.post_links:
            QDesktopServices.openUrl(QUrl(self.post_links[title]))

    def show_context_menu(self, position):
        """Показать контекстное меню"""
        item = self.list_widget.itemAt(position)
        if item and item.text() in self.post_links:
            menu = QMenu()
            menu.addAction("Открыть в браузере по-умолчанию")
            action = menu.exec(self.list_widget.mapToGlobal(position))
            if action:
                self.open_in_browser(item)
    
    def changeEvent(self, event):
        """Обработка сворачивания"""
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                self.hide()
                event.ignore()
        super().changeEvent(event)
    
    def tray_icon_activated(self, reason):
        """Обработка клика по иконке в трее"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("PikabuStartPage")
    app.setOrganizationName("PikabuStartPage")
    app.setDesktopFileName("pikabu-parser")
    window = PikabuThreadApp()
    window.show()
    sys.exit(app.exec())

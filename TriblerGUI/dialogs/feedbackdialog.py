from __future__ import absolute_import

import json
import os
from urllib import quote_plus
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QDialog, QTreeWidgetItem, QAction
import sys
import platform
import time

from six.moves import xrange
from PyQt5.QtWidgets import QMessageBox
from TriblerGUI.event_request_manager import received_events
from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.tribler_request_manager import performed_requests as tribler_performed_requests, TriblerRequestManager
from TriblerGUI.utilities import get_ui_file_path


class FeedbackDialog(QDialog):

    def __init__(self, parent, exception_text, tribler_version, start_time):
        QDialog.__init__(self, parent)

        uic.loadUi(get_ui_file_path('feedback_dialog.ui'), self)

        self.setWindowTitle("Unexpected error")
        self.selected_item_index = 0
        self.tribler_version = tribler_version
        self.request_mgr = None

        # Qt 5.2 does not have the setPlaceholderText property
        if hasattr(self.comments_text_edit, "setPlaceholderText"):
            self.comments_text_edit.setPlaceholderText("Comments (optional)")

        def add_item_to_info_widget(key, value):
            item = QTreeWidgetItem(self.env_variables_list)
            item.setText(0, key)
            item.setText(1, value)

        self.error_text_edit.setPlainText(exception_text.rstrip())

        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        self.send_report_button.clicked.connect(self.on_send_clicked)

        # Add machine information to the tree widget
        add_item_to_info_widget('os.getcwd', '%s' % os.getcwd())
        add_item_to_info_widget('sys.executable', '%s' % sys.executable)

        add_item_to_info_widget('os', os.name)
        add_item_to_info_widget('platform', sys.platform)
        add_item_to_info_widget('platform.details', platform.platform())
        add_item_to_info_widget('platform.machine', platform.machine())
        add_item_to_info_widget('python.version', sys.version)
        add_item_to_info_widget('indebug', str(__debug__))
        add_item_to_info_widget('tribler_uptime', "%s" % (time.time() - start_time))

        for argv in sys.argv:
            add_item_to_info_widget('sys.argv', '%s' % argv)

        for path in sys.path:
            add_item_to_info_widget('sys.path', '%s' % path)

        for key in os.environ.keys():
            add_item_to_info_widget('os.environ', '%s: %s' % (key, os.environ[key]))

        # Add recent requests to feedback dialog
        request_ind = 1
        for endpoint, method, data, timestamp, status_code in sorted(tribler_performed_requests,
                                                                     key=lambda x: x[3])[-30:]:
            add_item_to_info_widget('request_%d' % request_ind, '%s %s %s (time: %s, code: %s)' %
                                    (endpoint, method, data, timestamp, status_code))
            request_ind += 1

        # Add recent events to feedback dialog
        events_ind = 1
        for event, event_time in received_events[:30][::-1]:
            add_item_to_info_widget('event_%d' % events_ind, '%s (time: %s)' % (json.dumps(event), event_time))
            events_ind += 1

        # Users can remove specific lines in the report
        self.env_variables_list.customContextMenuRequested.connect(self.on_right_click_item)

    def on_remove_entry(self):
        self.env_variables_list.takeTopLevelItem(self.selected_item_index)

    def on_right_click_item(self, pos):
        item_clicked = self.env_variables_list.itemAt(pos)
        if not item_clicked:
            return

        self.selected_item_index = self.env_variables_list.indexOfTopLevelItem(item_clicked)

        menu = TriblerActionMenu(self)

        remove_action = QAction('Remove entry', self)
        remove_action.triggered.connect(self.on_remove_entry)
        menu.addAction(remove_action)
        menu.exec_(self.env_variables_list.mapToGlobal(pos))

    def on_cancel_clicked(self):
        QApplication.quit()

    def on_report_sent(self, response):
        if not response:
            return
        sent = response[u'sent']

        success_text = "Successfully sent the report! Thanks for your contribution."
        error_text = "Could not send the report! Please post this issue on GitHub."

        box = QMessageBox(self.window())
        box.setWindowTitle("Report Sent" if sent else "ERROR: Report Sending Failed")
        box.setText(success_text if sent else error_text)
        box.setStyleSheet("QPushButton { color: white; }")
        box.exec_()

        QApplication.quit()

    def on_send_clicked(self):
        self.send_report_button.setEnabled(False)
        self.send_report_button.setText("SENDING...")

        self.request_mgr = TriblerRequestManager()
        endpoint = 'http://reporter.tribler.org/report'

        sys_info = ""
        for ind in xrange(self.env_variables_list.topLevelItemCount()):
            item = self.env_variables_list.topLevelItem(ind)
            sys_info += "%s\t%s\n" % (quote_plus(item.text(0)), quote_plus(item.text(1)))

        comments = self.comments_text_edit.toPlainText()
        if len(comments) == 0:
            comments = "Not provided"
        comments = quote_plus(comments)

        stack = quote_plus(self.error_text_edit.toPlainText())

        post_data = "version=%s&machine=%s&os=%s&timestamp=%s&sysinfo=%s&comments=%s&stack=%s" % \
                    (self.tribler_version, platform.machine(), platform.platform(),
                     int(time.time()), sys_info, comments, stack)

        self.request_mgr.perform_request(endpoint, self.on_report_sent, data=str(post_data), method='POST')

    def closeEvent(self, close_event):
        QApplication.quit()
        close_event.ignore()

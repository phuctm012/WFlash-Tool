# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QPlainTextEdit, QProgressBar,
    QPushButton, QSizePolicy, QSpacerItem, QStatusBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1280, 820)
        self.centralWidget_main = QWidget(MainWindow)
        self.centralWidget_main.setObjectName(u"centralWidget_main")
        self.verticalLayout_main = QVBoxLayout(self.centralWidget_main)
        self.verticalLayout_main.setObjectName(u"verticalLayout_main")
        self.horizontalLayout_flashHeader = QHBoxLayout()
        self.horizontalLayout_flashHeader.setObjectName(u"horizontalLayout_flashHeader")
        self.pushButton_flash = QPushButton(self.centralWidget_main)
        self.pushButton_flash.setObjectName(u"pushButton_flash")
        self.pushButton_flash.setMinimumSize(QSize(90, 70))
        self.pushButton_flash.setMaximumSize(QSize(90, 70))

        self.horizontalLayout_flashHeader.addWidget(self.pushButton_flash)

        self.verticalLayout_flashProgress = QVBoxLayout()
        self.verticalLayout_flashProgress.setObjectName(u"verticalLayout_flashProgress")
        self.horizontalLayout_progressRow = QHBoxLayout()
        self.horizontalLayout_progressRow.setObjectName(u"horizontalLayout_progressRow")
        self.progressBar_flash = QProgressBar(self.centralWidget_main)
        self.progressBar_flash.setObjectName(u"progressBar_flash")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.progressBar_flash.sizePolicy().hasHeightForWidth())
        self.progressBar_flash.setSizePolicy(sizePolicy)
        self.progressBar_flash.setMinimumSize(QSize(0, 20))
        self.progressBar_flash.setMaximumSize(QSize(16777215, 20))
        self.progressBar_flash.setValue(0)
        self.progressBar_flash.setTextVisible(False)

        self.horizontalLayout_progressRow.addWidget(self.progressBar_flash)

        self.label_flashStats = QLabel(self.centralWidget_main)
        self.label_flashStats.setObjectName(u"label_flashStats")
        self.label_flashStats.setMinimumSize(QSize(280, 0))

        self.horizontalLayout_progressRow.addWidget(self.label_flashStats)


        self.verticalLayout_flashProgress.addLayout(self.horizontalLayout_progressRow)

        self.label_step = QLabel(self.centralWidget_main)
        self.label_step.setObjectName(u"label_step")

        self.verticalLayout_flashProgress.addWidget(self.label_step)


        self.horizontalLayout_flashHeader.addLayout(self.verticalLayout_flashProgress)


        self.verticalLayout_main.addLayout(self.horizontalLayout_flashHeader)

        self.label_rollbackWarning = QLabel(self.centralWidget_main)
        self.label_rollbackWarning.setObjectName(u"label_rollbackWarning")
        self.label_rollbackWarning.setVisible(False)
        self.label_rollbackWarning.setWordWrap(True)

        self.verticalLayout_main.addWidget(self.label_rollbackWarning)

        self.horizontalLayout_workArea = QHBoxLayout()
        self.horizontalLayout_workArea.setObjectName(u"horizontalLayout_workArea")
        self.frame_settingPanel = QFrame(self.centralWidget_main)
        self.frame_settingPanel.setObjectName(u"frame_settingPanel")
        self.frame_settingPanel.setMinimumSize(QSize(360, 0))
        self.frame_settingPanel.setMaximumSize(QSize(360, 16777215))
        self.frame_settingPanel.setFrameShape(QFrame.Shape.StyledPanel)
        self.verticalLayout_settingPanel = QVBoxLayout(self.frame_settingPanel)
        self.verticalLayout_settingPanel.setSpacing(0)
        self.verticalLayout_settingPanel.setObjectName(u"verticalLayout_settingPanel")
        self.verticalLayout_settingPanel.setContentsMargins(0, 0, 0, 0)
        self.label_settingHeader = QLabel(self.frame_settingPanel)
        self.label_settingHeader.setObjectName(u"label_settingHeader")

        self.verticalLayout_settingPanel.addWidget(self.label_settingHeader)

        self.gridLayout_setting = QGridLayout()
        self.gridLayout_setting.setObjectName(u"gridLayout_setting")
        self.gridLayout_setting.setVerticalSpacing(8)
        self.gridLayout_setting.setContentsMargins(10, 10, 10, 6)
        self.label_profile = QLabel(self.frame_settingPanel)
        self.label_profile.setObjectName(u"label_profile")

        self.gridLayout_setting.addWidget(self.label_profile, 0, 0, 1, 1)

        self.horizontalLayout_profile = QHBoxLayout()
        self.horizontalLayout_profile.setObjectName(u"horizontalLayout_profile")
        self.comboBox_profile = QComboBox(self.frame_settingPanel)
        self.comboBox_profile.setObjectName(u"comboBox_profile")
        sizePolicy.setHeightForWidth(self.comboBox_profile.sizePolicy().hasHeightForWidth())
        self.comboBox_profile.setSizePolicy(sizePolicy)

        self.horizontalLayout_profile.addWidget(self.comboBox_profile)

        self.pushButton_reloadProfiles = QPushButton(self.frame_settingPanel)
        self.pushButton_reloadProfiles.setObjectName(u"pushButton_reloadProfiles")

        self.horizontalLayout_profile.addWidget(self.pushButton_reloadProfiles)


        self.gridLayout_setting.addLayout(self.horizontalLayout_profile, 0, 1, 1, 1)

        self.label_firmwareSource = QLabel(self.frame_settingPanel)
        self.label_firmwareSource.setObjectName(u"label_firmwareSource")

        self.gridLayout_setting.addWidget(self.label_firmwareSource, 1, 0, 1, 1)

        self.pushButton_loadFromGitlab = QPushButton(self.frame_settingPanel)
        self.pushButton_loadFromGitlab.setObjectName(u"pushButton_loadFromGitlab")

        self.gridLayout_setting.addWidget(self.pushButton_loadFromGitlab, 1, 1, 1, 1)

        self.frame_sourceCard = QFrame(self.frame_settingPanel)
        self.frame_sourceCard.setObjectName(u"frame_sourceCard")
        self.frame_sourceCard.setFrameShape(QFrame.Shape.StyledPanel)
        self.verticalLayout_sourceCard = QVBoxLayout(self.frame_sourceCard)
        self.verticalLayout_sourceCard.setSpacing(2)
        self.verticalLayout_sourceCard.setObjectName(u"verticalLayout_sourceCard")
        self.label_sourceTitle = QLabel(self.frame_sourceCard)
        self.label_sourceTitle.setObjectName(u"label_sourceTitle")
        self.label_sourceTitle.setWordWrap(True)

        self.verticalLayout_sourceCard.addWidget(self.label_sourceTitle)

        self.label_sourceDetail = QLabel(self.frame_sourceCard)
        self.label_sourceDetail.setObjectName(u"label_sourceDetail")
        self.label_sourceDetail.setWordWrap(True)
        self.label_sourceDetail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.verticalLayout_sourceCard.addWidget(self.label_sourceDetail)

        self.label_sourceCache = QLabel(self.frame_sourceCard)
        self.label_sourceCache.setObjectName(u"label_sourceCache")

        self.verticalLayout_sourceCard.addWidget(self.label_sourceCache)


        self.gridLayout_setting.addWidget(self.frame_sourceCard, 2, 0, 1, 2)

        self.label_instance = QLabel(self.frame_settingPanel)
        self.label_instance.setObjectName(u"label_instance")

        self.gridLayout_setting.addWidget(self.label_instance, 3, 0, 1, 1)

        self.horizontalLayout_instance = QHBoxLayout()
        self.horizontalLayout_instance.setObjectName(u"horizontalLayout_instance")
        self.comboBox_instance = QComboBox(self.frame_settingPanel)
        self.comboBox_instance.setObjectName(u"comboBox_instance")
        sizePolicy.setHeightForWidth(self.comboBox_instance.sizePolicy().hasHeightForWidth())
        self.comboBox_instance.setSizePolicy(sizePolicy)

        self.horizontalLayout_instance.addWidget(self.comboBox_instance)

        self.pushButton_refreshInstances = QPushButton(self.frame_settingPanel)
        self.pushButton_refreshInstances.setObjectName(u"pushButton_refreshInstances")

        self.horizontalLayout_instance.addWidget(self.pushButton_refreshInstances)


        self.gridLayout_setting.addLayout(self.horizontalLayout_instance, 3, 1, 1, 1)

        self.label_afterFlash = QLabel(self.frame_settingPanel)
        self.label_afterFlash.setObjectName(u"label_afterFlash")

        self.gridLayout_setting.addWidget(self.label_afterFlash, 4, 0, 1, 1)

        self.horizontalLayout_afterFlash = QHBoxLayout()
        self.horizontalLayout_afterFlash.setObjectName(u"horizontalLayout_afterFlash")
        self.checkBox_reset = QCheckBox(self.frame_settingPanel)
        self.checkBox_reset.setObjectName(u"checkBox_reset")
        self.checkBox_reset.setChecked(True)

        self.horizontalLayout_afterFlash.addWidget(self.checkBox_reset)

        self.checkBox_run = QCheckBox(self.frame_settingPanel)
        self.checkBox_run.setObjectName(u"checkBox_run")

        self.horizontalLayout_afterFlash.addWidget(self.checkBox_run)


        self.gridLayout_setting.addLayout(self.horizontalLayout_afterFlash, 4, 1, 1, 1)


        self.verticalLayout_settingPanel.addLayout(self.gridLayout_setting)

        self.verticalSpacer_settingPanel = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_settingPanel.addItem(self.verticalSpacer_settingPanel)

        self.horizontalLayout_preferences = QHBoxLayout()
        self.horizontalLayout_preferences.setObjectName(u"horizontalLayout_preferences")
        self.horizontalLayout_preferences.setContentsMargins(10, -1, 10, 10)
        self.horizontalSpacer_preferences = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_preferences.addItem(self.horizontalSpacer_preferences)

        self.pushButton_preferences = QPushButton(self.frame_settingPanel)
        self.pushButton_preferences.setObjectName(u"pushButton_preferences")

        self.horizontalLayout_preferences.addWidget(self.pushButton_preferences)


        self.verticalLayout_settingPanel.addLayout(self.horizontalLayout_preferences)


        self.horizontalLayout_workArea.addWidget(self.frame_settingPanel)

        self.verticalLayout_mapping = QVBoxLayout()
        self.verticalLayout_mapping.setObjectName(u"verticalLayout_mapping")
        self.tableWidget_mapping = QTableWidget(self.centralWidget_main)
        if (self.tableWidget_mapping.columnCount() < 5):
            self.tableWidget_mapping.setColumnCount(5)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget_mapping.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget_mapping.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget_mapping.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.tableWidget_mapping.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.tableWidget_mapping.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        self.tableWidget_mapping.setObjectName(u"tableWidget_mapping")
        self.tableWidget_mapping.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableWidget_mapping.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tableWidget_mapping.horizontalHeader().setStretchLastSection(True)
        self.tableWidget_mapping.verticalHeader().setVisible(False)

        self.verticalLayout_mapping.addWidget(self.tableWidget_mapping)

        self.label_mappingHint = QLabel(self.centralWidget_main)
        self.label_mappingHint.setObjectName(u"label_mappingHint")

        self.verticalLayout_mapping.addWidget(self.label_mappingHint)


        self.horizontalLayout_workArea.addLayout(self.verticalLayout_mapping)


        self.verticalLayout_main.addLayout(self.horizontalLayout_workArea)

        self.tabWidget_output = QTabWidget(self.centralWidget_main)
        self.tabWidget_output.setObjectName(u"tabWidget_output")
        self.tab_information = QWidget()
        self.tab_information.setObjectName(u"tab_information")
        self.verticalLayout_information = QVBoxLayout(self.tab_information)
        self.verticalLayout_information.setObjectName(u"verticalLayout_information")
        self.horizontalLayout_logBar = QHBoxLayout()
        self.horizontalLayout_logBar.setObjectName(u"horizontalLayout_logBar")
        self.label_logLevel = QLabel(self.tab_information)
        self.label_logLevel.setObjectName(u"label_logLevel")

        self.horizontalLayout_logBar.addWidget(self.label_logLevel)

        self.comboBox_logLevel = QComboBox(self.tab_information)
        self.comboBox_logLevel.addItem("")
        self.comboBox_logLevel.addItem("")
        self.comboBox_logLevel.addItem("")
        self.comboBox_logLevel.addItem("")
        self.comboBox_logLevel.setObjectName(u"comboBox_logLevel")

        self.horizontalLayout_logBar.addWidget(self.comboBox_logLevel)

        self.horizontalSpacer_logBar = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_logBar.addItem(self.horizontalSpacer_logBar)

        self.pushButton_copyLog = QPushButton(self.tab_information)
        self.pushButton_copyLog.setObjectName(u"pushButton_copyLog")

        self.horizontalLayout_logBar.addWidget(self.pushButton_copyLog)

        self.pushButton_clearLog = QPushButton(self.tab_information)
        self.pushButton_clearLog.setObjectName(u"pushButton_clearLog")

        self.horizontalLayout_logBar.addWidget(self.pushButton_clearLog)

        self.pushButton_exportBundle = QPushButton(self.tab_information)
        self.pushButton_exportBundle.setObjectName(u"pushButton_exportBundle")

        self.horizontalLayout_logBar.addWidget(self.pushButton_exportBundle)


        self.verticalLayout_information.addLayout(self.horizontalLayout_logBar)

        self.plainTextEdit_log = QPlainTextEdit(self.tab_information)
        self.plainTextEdit_log.setObjectName(u"plainTextEdit_log")
        self.plainTextEdit_log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.plainTextEdit_log.setReadOnly(True)
        self.plainTextEdit_log.setMaximumBlockCount(20000)

        self.verticalLayout_information.addWidget(self.plainTextEdit_log)

        self.tabWidget_output.addTab(self.tab_information, "")

        self.verticalLayout_main.addWidget(self.tabWidget_output)

        self.verticalLayout_main.setStretch(2, 3)
        self.verticalLayout_main.setStretch(3, 2)
        MainWindow.setCentralWidget(self.centralWidget_main)
        self.statusBar_main = QStatusBar(MainWindow)
        self.statusBar_main.setObjectName(u"statusBar_main")
        MainWindow.setStatusBar(self.statusBar_main)
#if QT_CONFIG(shortcut)
        self.label_profile.setBuddy(self.comboBox_profile)
        self.label_firmwareSource.setBuddy(self.pushButton_loadFromGitlab)
        self.label_instance.setBuddy(self.comboBox_instance)
        self.label_logLevel.setBuddy(self.comboBox_logLevel)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(MainWindow)

        self.tabWidget_output.setCurrentIndex(0)
        self.comboBox_logLevel.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"WFlash", None))
        self.pushButton_flash.setText(QCoreApplication.translate("MainWindow", u"Flash", None))
        self.pushButton_flash.setProperty(u"state", QCoreApplication.translate("MainWindow", u"idle", None))
        self.label_flashStats.setText(QCoreApplication.translate("MainWindow", u"ETA: -- | Speed: --", None))
        self.label_step.setText(QCoreApplication.translate("MainWindow", u"Step: Idle", None))
        self.label_rollbackWarning.setText(QCoreApplication.translate("MainWindow", u"ROLLBACK FAILED \u2014 the winIDEA workspace may still point to the new files. Check the download and symbol file list in winIDEA before flashing again.", None))
        self.label_settingHeader.setText(QCoreApplication.translate("MainWindow", u"Setting", None))
        self.label_profile.setText(QCoreApplication.translate("MainWindow", u"Profile", None))
        self.pushButton_reloadProfiles.setText(QCoreApplication.translate("MainWindow", u"Reload", None))
        self.label_firmwareSource.setText(QCoreApplication.translate("MainWindow", u"Firmware source", None))
        self.pushButton_loadFromGitlab.setText(QCoreApplication.translate("MainWindow", u"Load from GitLab\u2026", None))
        self.label_sourceTitle.setText(QCoreApplication.translate("MainWindow", u"No firmware loaded \u2014 use Load from GitLab\u2026", None))
        self.label_sourceDetail.setText("")
        self.label_sourceCache.setText("")
        self.label_instance.setText(QCoreApplication.translate("MainWindow", u"winIDEA", None))
        self.pushButton_refreshInstances.setText(QCoreApplication.translate("MainWindow", u"Refresh", None))
        self.label_afterFlash.setText(QCoreApplication.translate("MainWindow", u"After flash", None))
        self.checkBox_reset.setText(QCoreApplication.translate("MainWindow", u"Reset target", None))
        self.checkBox_run.setText(QCoreApplication.translate("MainWindow", u"Run after reset", None))
        self.pushButton_preferences.setText(QCoreApplication.translate("MainWindow", u"Preferences\u2026", None))
        ___qtablewidgetitem = self.tableWidget_mapping.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"#", None))
        ___qtablewidgetitem1 = self.tableWidget_mapping.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"Type", None))
        ___qtablewidgetitem2 = self.tableWidget_mapping.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindow", u"winIDEA target", None))
        ___qtablewidgetitem3 = self.tableWidget_mapping.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindow", u"Pattern", None))
        ___qtablewidgetitem4 = self.tableWidget_mapping.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("MainWindow", u"File", None))
        self.label_mappingHint.setText(QCoreApplication.translate("MainWindow", u"Load firmware to fill the mapping.", None))
        self.label_logLevel.setText(QCoreApplication.translate("MainWindow", u"Log level", None))
        self.comboBox_logLevel.setItemText(0, QCoreApplication.translate("MainWindow", u"DEBUG", None))
        self.comboBox_logLevel.setItemText(1, QCoreApplication.translate("MainWindow", u"INFO", None))
        self.comboBox_logLevel.setItemText(2, QCoreApplication.translate("MainWindow", u"WARNING", None))
        self.comboBox_logLevel.setItemText(3, QCoreApplication.translate("MainWindow", u"ERROR", None))

        self.pushButton_copyLog.setText(QCoreApplication.translate("MainWindow", u"Copy", None))
        self.pushButton_clearLog.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.pushButton_exportBundle.setText(QCoreApplication.translate("MainWindow", u"Export debug bundle\u2026", None))
        self.tabWidget_output.setTabText(self.tabWidget_output.indexOf(self.tab_information), QCoreApplication.translate("MainWindow", u"Information", None))
    # retranslateUi


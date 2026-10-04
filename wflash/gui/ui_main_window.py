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
    QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit,
    QProgressBar, QPushButton, QSizePolicy, QSpacerItem,
    QSplitter, QStatusBar, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1280, 820)
        self.centralWidget_main = QWidget(MainWindow)
        self.centralWidget_main.setObjectName(u"centralWidget_main")
        self.verticalLayout_main = QVBoxLayout(self.centralWidget_main)
        self.verticalLayout_main.setObjectName(u"verticalLayout_main")
        self.horizontalLayout_profileBar = QHBoxLayout()
        self.horizontalLayout_profileBar.setObjectName(u"horizontalLayout_profileBar")
        self.label_profile = QLabel(self.centralWidget_main)
        self.label_profile.setObjectName(u"label_profile")

        self.horizontalLayout_profileBar.addWidget(self.label_profile)

        self.comboBox_profile = QComboBox(self.centralWidget_main)
        self.comboBox_profile.setObjectName(u"comboBox_profile")
        self.comboBox_profile.setMinimumSize(QSize(220, 0))

        self.horizontalLayout_profileBar.addWidget(self.comboBox_profile)

        self.pushButton_reloadProfiles = QPushButton(self.centralWidget_main)
        self.pushButton_reloadProfiles.setObjectName(u"pushButton_reloadProfiles")

        self.horizontalLayout_profileBar.addWidget(self.pushButton_reloadProfiles)

        self.horizontalSpacer_profileBar = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_profileBar.addItem(self.horizontalSpacer_profileBar)

        self.pushButton_settings = QPushButton(self.centralWidget_main)
        self.pushButton_settings.setObjectName(u"pushButton_settings")

        self.horizontalLayout_profileBar.addWidget(self.pushButton_settings)


        self.verticalLayout_main.addLayout(self.horizontalLayout_profileBar)

        self.splitter_mainVertical = QSplitter(self.centralWidget_main)
        self.splitter_mainVertical.setObjectName(u"splitter_mainVertical")
        self.splitter_mainVertical.setOrientation(Qt.Orientation.Vertical)
        self.splitter_upperHorizontal = QSplitter(self.splitter_mainVertical)
        self.splitter_upperHorizontal.setObjectName(u"splitter_upperHorizontal")
        self.splitter_upperHorizontal.setOrientation(Qt.Orientation.Horizontal)
        self.groupBox_gitlab = QGroupBox(self.splitter_upperHorizontal)
        self.groupBox_gitlab.setObjectName(u"groupBox_gitlab")
        self.verticalLayout_gitlabBrowser = QVBoxLayout(self.groupBox_gitlab)
        self.verticalLayout_gitlabBrowser.setObjectName(u"verticalLayout_gitlabBrowser")
        self.label_project = QLabel(self.groupBox_gitlab)
        self.label_project.setObjectName(u"label_project")

        self.verticalLayout_gitlabBrowser.addWidget(self.label_project)

        self.horizontalLayout_refBar = QHBoxLayout()
        self.horizontalLayout_refBar.setObjectName(u"horizontalLayout_refBar")
        self.label_ref = QLabel(self.groupBox_gitlab)
        self.label_ref.setObjectName(u"label_ref")

        self.horizontalLayout_refBar.addWidget(self.label_ref)

        self.comboBox_ref = QComboBox(self.groupBox_gitlab)
        self.comboBox_ref.setObjectName(u"comboBox_ref")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.comboBox_ref.sizePolicy().hasHeightForWidth())
        self.comboBox_ref.setSizePolicy(sizePolicy)

        self.horizontalLayout_refBar.addWidget(self.comboBox_ref)

        self.pushButton_refreshRefs = QPushButton(self.groupBox_gitlab)
        self.pushButton_refreshRefs.setObjectName(u"pushButton_refreshRefs")

        self.horizontalLayout_refBar.addWidget(self.pushButton_refreshRefs)


        self.verticalLayout_gitlabBrowser.addLayout(self.horizontalLayout_refBar)

        self.label_pipelines = QLabel(self.groupBox_gitlab)
        self.label_pipelines.setObjectName(u"label_pipelines")

        self.verticalLayout_gitlabBrowser.addWidget(self.label_pipelines)

        self.listWidget_pipelines = QListWidget(self.groupBox_gitlab)
        self.listWidget_pipelines.setObjectName(u"listWidget_pipelines")

        self.verticalLayout_gitlabBrowser.addWidget(self.listWidget_pipelines)

        self.label_jobs = QLabel(self.groupBox_gitlab)
        self.label_jobs.setObjectName(u"label_jobs")

        self.verticalLayout_gitlabBrowser.addWidget(self.label_jobs)

        self.listWidget_jobs = QListWidget(self.groupBox_gitlab)
        self.listWidget_jobs.setObjectName(u"listWidget_jobs")

        self.verticalLayout_gitlabBrowser.addWidget(self.listWidget_jobs)

        self.horizontalLayout_artifactDownload = QHBoxLayout()
        self.horizontalLayout_artifactDownload.setObjectName(u"horizontalLayout_artifactDownload")
        self.progressBar_artifact = QProgressBar(self.groupBox_gitlab)
        self.progressBar_artifact.setObjectName(u"progressBar_artifact")
        self.progressBar_artifact.setValue(0)

        self.horizontalLayout_artifactDownload.addWidget(self.progressBar_artifact)

        self.pushButton_cancelArtifact = QPushButton(self.groupBox_gitlab)
        self.pushButton_cancelArtifact.setObjectName(u"pushButton_cancelArtifact")

        self.horizontalLayout_artifactDownload.addWidget(self.pushButton_cancelArtifact)

        self.pushButton_downloadArtifact = QPushButton(self.groupBox_gitlab)
        self.pushButton_downloadArtifact.setObjectName(u"pushButton_downloadArtifact")

        self.horizontalLayout_artifactDownload.addWidget(self.pushButton_downloadArtifact)


        self.verticalLayout_gitlabBrowser.addLayout(self.horizontalLayout_artifactDownload)

        self.splitter_upperHorizontal.addWidget(self.groupBox_gitlab)
        self.widget_rightColumn = QWidget(self.splitter_upperHorizontal)
        self.widget_rightColumn.setObjectName(u"widget_rightColumn")
        self.verticalLayout_rightColumn = QVBoxLayout(self.widget_rightColumn)
        self.verticalLayout_rightColumn.setObjectName(u"verticalLayout_rightColumn")
        self.verticalLayout_rightColumn.setContentsMargins(0, 0, 0, 0)
        self.groupBox_mapping = QGroupBox(self.widget_rightColumn)
        self.groupBox_mapping.setObjectName(u"groupBox_mapping")
        self.verticalLayout_mapping = QVBoxLayout(self.groupBox_mapping)
        self.verticalLayout_mapping.setObjectName(u"verticalLayout_mapping")
        self.label_artifact = QLabel(self.groupBox_mapping)
        self.label_artifact.setObjectName(u"label_artifact")
        self.label_artifact.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.verticalLayout_mapping.addWidget(self.label_artifact)

        self.tableWidget_mapping = QTableWidget(self.groupBox_mapping)
        if (self.tableWidget_mapping.columnCount() < 4):
            self.tableWidget_mapping.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget_mapping.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget_mapping.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget_mapping.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.tableWidget_mapping.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.tableWidget_mapping.setObjectName(u"tableWidget_mapping")
        self.tableWidget_mapping.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableWidget_mapping.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tableWidget_mapping.horizontalHeader().setStretchLastSection(True)
        self.tableWidget_mapping.verticalHeader().setVisible(False)

        self.verticalLayout_mapping.addWidget(self.tableWidget_mapping)


        self.verticalLayout_rightColumn.addWidget(self.groupBox_mapping)

        self.groupBox_flash = QGroupBox(self.widget_rightColumn)
        self.groupBox_flash.setObjectName(u"groupBox_flash")
        self.verticalLayout_flash = QVBoxLayout(self.groupBox_flash)
        self.verticalLayout_flash.setObjectName(u"verticalLayout_flash")
        self.horizontalLayout_instance = QHBoxLayout()
        self.horizontalLayout_instance.setObjectName(u"horizontalLayout_instance")
        self.label_instance = QLabel(self.groupBox_flash)
        self.label_instance.setObjectName(u"label_instance")

        self.horizontalLayout_instance.addWidget(self.label_instance)

        self.comboBox_instance = QComboBox(self.groupBox_flash)
        self.comboBox_instance.setObjectName(u"comboBox_instance")
        sizePolicy.setHeightForWidth(self.comboBox_instance.sizePolicy().hasHeightForWidth())
        self.comboBox_instance.setSizePolicy(sizePolicy)

        self.horizontalLayout_instance.addWidget(self.comboBox_instance)

        self.pushButton_refreshInstances = QPushButton(self.groupBox_flash)
        self.pushButton_refreshInstances.setObjectName(u"pushButton_refreshInstances")

        self.horizontalLayout_instance.addWidget(self.pushButton_refreshInstances)


        self.verticalLayout_flash.addLayout(self.horizontalLayout_instance)

        self.horizontalLayout_flashButtons = QHBoxLayout()
        self.horizontalLayout_flashButtons.setObjectName(u"horizontalLayout_flashButtons")
        self.checkBox_reset = QCheckBox(self.groupBox_flash)
        self.checkBox_reset.setObjectName(u"checkBox_reset")
        self.checkBox_reset.setChecked(True)

        self.horizontalLayout_flashButtons.addWidget(self.checkBox_reset)

        self.checkBox_run = QCheckBox(self.groupBox_flash)
        self.checkBox_run.setObjectName(u"checkBox_run")

        self.horizontalLayout_flashButtons.addWidget(self.checkBox_run)

        self.horizontalSpacer_flashButtons = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_flashButtons.addItem(self.horizontalSpacer_flashButtons)

        self.pushButton_cancelFlash = QPushButton(self.groupBox_flash)
        self.pushButton_cancelFlash.setObjectName(u"pushButton_cancelFlash")

        self.horizontalLayout_flashButtons.addWidget(self.pushButton_cancelFlash)

        self.pushButton_flash = QPushButton(self.groupBox_flash)
        self.pushButton_flash.setObjectName(u"pushButton_flash")

        self.horizontalLayout_flashButtons.addWidget(self.pushButton_flash)


        self.verticalLayout_flash.addLayout(self.horizontalLayout_flashButtons)

        self.horizontalLayout_flashStatus = QHBoxLayout()
        self.horizontalLayout_flashStatus.setObjectName(u"horizontalLayout_flashStatus")
        self.label_step = QLabel(self.groupBox_flash)
        self.label_step.setObjectName(u"label_step")

        self.horizontalLayout_flashStatus.addWidget(self.label_step)

        self.progressBar_flash = QProgressBar(self.groupBox_flash)
        self.progressBar_flash.setObjectName(u"progressBar_flash")
        sizePolicy.setHeightForWidth(self.progressBar_flash.sizePolicy().hasHeightForWidth())
        self.progressBar_flash.setSizePolicy(sizePolicy)
        self.progressBar_flash.setValue(0)

        self.horizontalLayout_flashStatus.addWidget(self.progressBar_flash)


        self.verticalLayout_flash.addLayout(self.horizontalLayout_flashStatus)

        self.label_rollbackWarning = QLabel(self.groupBox_flash)
        self.label_rollbackWarning.setObjectName(u"label_rollbackWarning")
        self.label_rollbackWarning.setVisible(False)
        self.label_rollbackWarning.setStyleSheet(u"color: #d32f2f; font-weight: bold;")
        self.label_rollbackWarning.setWordWrap(True)

        self.verticalLayout_flash.addWidget(self.label_rollbackWarning)


        self.verticalLayout_rightColumn.addWidget(self.groupBox_flash)

        self.splitter_upperHorizontal.addWidget(self.widget_rightColumn)
        self.splitter_mainVertical.addWidget(self.splitter_upperHorizontal)
        self.groupBox_log = QGroupBox(self.splitter_mainVertical)
        self.groupBox_log.setObjectName(u"groupBox_log")
        self.verticalLayout_logPanel = QVBoxLayout(self.groupBox_log)
        self.verticalLayout_logPanel.setObjectName(u"verticalLayout_logPanel")
        self.horizontalLayout_logBar = QHBoxLayout()
        self.horizontalLayout_logBar.setObjectName(u"horizontalLayout_logBar")
        self.label_logLevel = QLabel(self.groupBox_log)
        self.label_logLevel.setObjectName(u"label_logLevel")

        self.horizontalLayout_logBar.addWidget(self.label_logLevel)

        self.comboBox_logLevel = QComboBox(self.groupBox_log)
        self.comboBox_logLevel.addItem("")
        self.comboBox_logLevel.addItem("")
        self.comboBox_logLevel.addItem("")
        self.comboBox_logLevel.addItem("")
        self.comboBox_logLevel.setObjectName(u"comboBox_logLevel")

        self.horizontalLayout_logBar.addWidget(self.comboBox_logLevel)

        self.horizontalSpacer_logBar = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_logBar.addItem(self.horizontalSpacer_logBar)

        self.pushButton_copyLog = QPushButton(self.groupBox_log)
        self.pushButton_copyLog.setObjectName(u"pushButton_copyLog")

        self.horizontalLayout_logBar.addWidget(self.pushButton_copyLog)

        self.pushButton_clearLog = QPushButton(self.groupBox_log)
        self.pushButton_clearLog.setObjectName(u"pushButton_clearLog")

        self.horizontalLayout_logBar.addWidget(self.pushButton_clearLog)

        self.pushButton_exportBundle = QPushButton(self.groupBox_log)
        self.pushButton_exportBundle.setObjectName(u"pushButton_exportBundle")

        self.horizontalLayout_logBar.addWidget(self.pushButton_exportBundle)


        self.verticalLayout_logPanel.addLayout(self.horizontalLayout_logBar)

        self.plainTextEdit_log = QPlainTextEdit(self.groupBox_log)
        self.plainTextEdit_log.setObjectName(u"plainTextEdit_log")
        self.plainTextEdit_log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.plainTextEdit_log.setReadOnly(True)
        self.plainTextEdit_log.setMaximumBlockCount(20000)

        self.verticalLayout_logPanel.addWidget(self.plainTextEdit_log)

        self.splitter_mainVertical.addWidget(self.groupBox_log)

        self.verticalLayout_main.addWidget(self.splitter_mainVertical)

        MainWindow.setCentralWidget(self.centralWidget_main)
        self.statusBar_main = QStatusBar(MainWindow)
        self.statusBar_main.setObjectName(u"statusBar_main")
        MainWindow.setStatusBar(self.statusBar_main)
#if QT_CONFIG(shortcut)
        self.label_profile.setBuddy(self.comboBox_profile)
        self.label_ref.setBuddy(self.comboBox_ref)
        self.label_pipelines.setBuddy(self.listWidget_pipelines)
        self.label_jobs.setBuddy(self.listWidget_jobs)
        self.label_instance.setBuddy(self.comboBox_instance)
        self.label_logLevel.setBuddy(self.comboBox_logLevel)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(MainWindow)

        self.comboBox_logLevel.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"WFlash \u2014 winIDEA ECU flasher", None))
        self.label_profile.setText(QCoreApplication.translate("MainWindow", u"Profile:", None))
        self.pushButton_reloadProfiles.setText(QCoreApplication.translate("MainWindow", u"Reload", None))
        self.pushButton_settings.setText(QCoreApplication.translate("MainWindow", u"Settings\u2026", None))
        self.groupBox_gitlab.setTitle(QCoreApplication.translate("MainWindow", u"1. GitLab artifact", None))
        self.label_project.setText(QCoreApplication.translate("MainWindow", u"No profile", None))
        self.label_ref.setText(QCoreApplication.translate("MainWindow", u"Branch/tag:", None))
        self.pushButton_refreshRefs.setText(QCoreApplication.translate("MainWindow", u"Refresh", None))
        self.label_pipelines.setText(QCoreApplication.translate("MainWindow", u"Pipelines:", None))
        self.label_jobs.setText(QCoreApplication.translate("MainWindow", u"Jobs with artifacts:", None))
        self.pushButton_cancelArtifact.setText(QCoreApplication.translate("MainWindow", u"Cancel", None))
        self.pushButton_downloadArtifact.setText(QCoreApplication.translate("MainWindow", u"Download artifact", None))
        self.groupBox_mapping.setTitle(QCoreApplication.translate("MainWindow", u"2. Files \u2192 winIDEA", None))
        self.label_artifact.setText(QCoreApplication.translate("MainWindow", u"No artifact loaded", None))
        ___qtablewidgetitem = self.tableWidget_mapping.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"Type", None))
        ___qtablewidgetitem1 = self.tableWidget_mapping.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"winIDEA target", None))
        ___qtablewidgetitem2 = self.tableWidget_mapping.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindow", u"Pattern", None))
        ___qtablewidgetitem3 = self.tableWidget_mapping.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindow", u"File", None))
        self.groupBox_flash.setTitle(QCoreApplication.translate("MainWindow", u"3. Flash", None))
        self.label_instance.setText(QCoreApplication.translate("MainWindow", u"winIDEA instance:", None))
        self.pushButton_refreshInstances.setText(QCoreApplication.translate("MainWindow", u"Refresh", None))
        self.checkBox_reset.setText(QCoreApplication.translate("MainWindow", u"Reset after flash", None))
        self.checkBox_run.setText(QCoreApplication.translate("MainWindow", u"Run after reset", None))
        self.pushButton_cancelFlash.setText(QCoreApplication.translate("MainWindow", u"Cancel", None))
        self.pushButton_flash.setText(QCoreApplication.translate("MainWindow", u"Flash", None))
        self.label_step.setText(QCoreApplication.translate("MainWindow", u"Idle", None))
        self.label_rollbackWarning.setText(QCoreApplication.translate("MainWindow", u"ROLLBACK FAILED \u2014 the winIDEA workspace may still point to the new files. Check the download and symbol file list in winIDEA before flashing again.", None))
        self.groupBox_log.setTitle(QCoreApplication.translate("MainWindow", u"Log", None))
        self.label_logLevel.setText(QCoreApplication.translate("MainWindow", u"Log level:", None))
        self.comboBox_logLevel.setItemText(0, QCoreApplication.translate("MainWindow", u"DEBUG", None))
        self.comboBox_logLevel.setItemText(1, QCoreApplication.translate("MainWindow", u"INFO", None))
        self.comboBox_logLevel.setItemText(2, QCoreApplication.translate("MainWindow", u"WARNING", None))
        self.comboBox_logLevel.setItemText(3, QCoreApplication.translate("MainWindow", u"ERROR", None))

        self.pushButton_copyLog.setText(QCoreApplication.translate("MainWindow", u"Copy", None))
        self.pushButton_clearLog.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.pushButton_exportBundle.setText(QCoreApplication.translate("MainWindow", u"Export debug bundle\u2026", None))
    # retranslateUi


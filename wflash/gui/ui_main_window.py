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
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMenu, QMenuBar, QPlainTextEdit, QProgressBar,
    QPushButton, QRadioButton, QScrollArea, QSizePolicy,
    QSpacerItem, QStatusBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1280, 860)
        self.action_exportBundle = QAction(MainWindow)
        self.action_exportBundle.setObjectName(u"action_exportBundle")
        self.action_openHistory = QAction(MainWindow)
        self.action_openHistory.setObjectName(u"action_openHistory")
        self.action_openLogFolder = QAction(MainWindow)
        self.action_openLogFolder.setObjectName(u"action_openLogFolder")
        self.action_openDownloadFolder = QAction(MainWindow)
        self.action_openDownloadFolder.setObjectName(u"action_openDownloadFolder")
        self.action_exit = QAction(MainWindow)
        self.action_exit.setObjectName(u"action_exit")
        self.action_darkMode = QAction(MainWindow)
        self.action_darkMode.setObjectName(u"action_darkMode")
        self.action_darkMode.setCheckable(True)
        self.action_tabFlash = QAction(MainWindow)
        self.action_tabFlash.setObjectName(u"action_tabFlash")
        self.action_tabGitlab = QAction(MainWindow)
        self.action_tabGitlab.setObjectName(u"action_tabGitlab")
        self.action_tabSetting = QAction(MainWindow)
        self.action_tabSetting.setObjectName(u"action_tabSetting")
        self.action_testGitlab = QAction(MainWindow)
        self.action_testGitlab.setObjectName(u"action_testGitlab")
        self.action_checkCores = QAction(MainWindow)
        self.action_checkCores.setObjectName(u"action_checkCores")
        self.action_refreshInstances = QAction(MainWindow)
        self.action_refreshInstances.setObjectName(u"action_refreshInstances")
        self.action_userGuide = QAction(MainWindow)
        self.action_userGuide.setObjectName(u"action_userGuide")
        self.action_about = QAction(MainWindow)
        self.action_about.setObjectName(u"action_about")
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

        self.label_commitWarning = QLabel(self.centralWidget_main)
        self.label_commitWarning.setObjectName(u"label_commitWarning")
        self.label_commitWarning.setVisible(False)
        self.label_commitWarning.setWordWrap(True)

        self.verticalLayout_main.addWidget(self.label_commitWarning)

        self.label_flashBlocked = QLabel(self.centralWidget_main)
        self.label_flashBlocked.setObjectName(u"label_flashBlocked")
        self.label_flashBlocked.setWordWrap(True)
        self.label_flashBlocked.setVisible(False)

        self.verticalLayout_main.addWidget(self.label_flashBlocked)

        self.tabWidget_main = QTabWidget(self.centralWidget_main)
        self.tabWidget_main.setObjectName(u"tabWidget_main")
        self.tab_flash = QWidget()
        self.tab_flash.setObjectName(u"tab_flash")
        self.horizontalLayout_flashTab = QHBoxLayout(self.tab_flash)
        self.horizontalLayout_flashTab.setObjectName(u"horizontalLayout_flashTab")
        self.frame_flashPanel = QFrame(self.tab_flash)
        self.frame_flashPanel.setObjectName(u"frame_flashPanel")
        self.frame_flashPanel.setMinimumSize(QSize(360, 0))
        self.frame_flashPanel.setMaximumSize(QSize(360, 16777215))
        self.frame_flashPanel.setFrameShape(QFrame.Shape.NoFrame)
        self.verticalLayout_flashPanel = QVBoxLayout(self.frame_flashPanel)
        self.verticalLayout_flashPanel.setSpacing(0)
        self.verticalLayout_flashPanel.setObjectName(u"verticalLayout_flashPanel")
        self.verticalLayout_flashPanel.setContentsMargins(0, 0, 0, 0)
        self.scrollArea_flashPanel = QScrollArea(self.frame_flashPanel)
        self.scrollArea_flashPanel.setObjectName(u"scrollArea_flashPanel")
        self.scrollArea_flashPanel.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea_flashPanel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scrollArea_flashPanel.setWidgetResizable(True)
        self.scrollAreaWidgetContents_flashPanel = QWidget()
        self.scrollAreaWidgetContents_flashPanel.setObjectName(u"scrollAreaWidgetContents_flashPanel")
        self.verticalLayout_flashScroll = QVBoxLayout(self.scrollAreaWidgetContents_flashPanel)
        self.verticalLayout_flashScroll.setSpacing(9)
        self.verticalLayout_flashScroll.setObjectName(u"verticalLayout_flashScroll")
        self.verticalLayout_flashScroll.setContentsMargins(2, 2, 6, 2)
        self.frame_firmwareSummary = QFrame(self.scrollAreaWidgetContents_flashPanel)
        self.frame_firmwareSummary.setObjectName(u"frame_firmwareSummary")
        self.frame_firmwareSummary.setFrameShape(QFrame.Shape.StyledPanel)
        self.verticalLayout_firmwareSummary = QVBoxLayout(self.frame_firmwareSummary)
        self.verticalLayout_firmwareSummary.setSpacing(8)
        self.verticalLayout_firmwareSummary.setObjectName(u"verticalLayout_firmwareSummary")
        self.verticalLayout_firmwareSummary.setContentsMargins(12, 10, 12, 10)
        self.label_summaryHeader = QLabel(self.frame_firmwareSummary)
        self.label_summaryHeader.setObjectName(u"label_summaryHeader")

        self.verticalLayout_firmwareSummary.addWidget(self.label_summaryHeader)

        self.label_summaryApp = QLabel(self.frame_firmwareSummary)
        self.label_summaryApp.setObjectName(u"label_summaryApp")
        self.label_summaryApp.setWordWrap(True)
        self.label_summaryApp.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label_summaryApp.setTextFormat(Qt.TextFormat.RichText)

        self.verticalLayout_firmwareSummary.addWidget(self.label_summaryApp)

        self.label_summaryBm = QLabel(self.frame_firmwareSummary)
        self.label_summaryBm.setObjectName(u"label_summaryBm")
        self.label_summaryBm.setWordWrap(True)
        self.label_summaryBm.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label_summaryBm.setTextFormat(Qt.TextFormat.RichText)

        self.verticalLayout_firmwareSummary.addWidget(self.label_summaryBm)

        self.label_summaryFbl = QLabel(self.frame_firmwareSummary)
        self.label_summaryFbl.setObjectName(u"label_summaryFbl")
        self.label_summaryFbl.setWordWrap(True)
        self.label_summaryFbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label_summaryFbl.setTextFormat(Qt.TextFormat.RichText)

        self.verticalLayout_firmwareSummary.addWidget(self.label_summaryFbl)

        self.label_summaryAdvanced = QLabel(self.frame_firmwareSummary)
        self.label_summaryAdvanced.setObjectName(u"label_summaryAdvanced")

        self.verticalLayout_firmwareSummary.addWidget(self.label_summaryAdvanced)


        self.verticalLayout_flashScroll.addWidget(self.frame_firmwareSummary)

        self.frame_gitlabSource = QFrame(self.scrollAreaWidgetContents_flashPanel)
        self.frame_gitlabSource.setObjectName(u"frame_gitlabSource")
        self.frame_gitlabSource.setFrameShape(QFrame.Shape.NoFrame)
        self.verticalLayout_gitlabSource = QVBoxLayout(self.frame_gitlabSource)
        self.verticalLayout_gitlabSource.setSpacing(8)
        self.verticalLayout_gitlabSource.setObjectName(u"verticalLayout_gitlabSource")
        self.verticalLayout_gitlabSource.setContentsMargins(0, 0, 0, 0)
        self.label_firmwareSource = QLabel(self.frame_gitlabSource)
        self.label_firmwareSource.setObjectName(u"label_firmwareSource")

        self.verticalLayout_gitlabSource.addWidget(self.label_firmwareSource)

        self.pushButton_loadFromGitlab = QPushButton(self.frame_gitlabSource)
        self.pushButton_loadFromGitlab.setObjectName(u"pushButton_loadFromGitlab")

        self.verticalLayout_gitlabSource.addWidget(self.pushButton_loadFromGitlab)

        self.frame_sourceCard = QFrame(self.frame_gitlabSource)
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

        self.verticalLayout_sourceSlots = QVBoxLayout()
        self.verticalLayout_sourceSlots.setSpacing(6)
        self.verticalLayout_sourceSlots.setObjectName(u"verticalLayout_sourceSlots")

        self.verticalLayout_sourceCard.addLayout(self.verticalLayout_sourceSlots)


        self.verticalLayout_gitlabSource.addWidget(self.frame_sourceCard)


        self.verticalLayout_flashScroll.addWidget(self.frame_gitlabSource)

        self.verticalSpacer_flashPanel = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_flashScroll.addItem(self.verticalSpacer_flashPanel)

        self.scrollArea_flashPanel.setWidget(self.scrollAreaWidgetContents_flashPanel)

        self.verticalLayout_flashPanel.addWidget(self.scrollArea_flashPanel)


        self.horizontalLayout_flashTab.addWidget(self.frame_flashPanel)

        self.verticalLayout_mapping = QVBoxLayout()
        self.verticalLayout_mapping.setObjectName(u"verticalLayout_mapping")
        self.label_programFiles = QLabel(self.tab_flash)
        self.label_programFiles.setObjectName(u"label_programFiles")

        self.verticalLayout_mapping.addWidget(self.label_programFiles)

        self.tableWidget_programFiles = QTableWidget(self.tab_flash)
        if (self.tableWidget_programFiles.columnCount() < 4):
            self.tableWidget_programFiles.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget_programFiles.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget_programFiles.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget_programFiles.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.tableWidget_programFiles.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.tableWidget_programFiles.setObjectName(u"tableWidget_programFiles")
        self.tableWidget_programFiles.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableWidget_programFiles.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tableWidget_programFiles.horizontalHeader().setStretchLastSection(True)
        self.tableWidget_programFiles.verticalHeader().setVisible(False)

        self.verticalLayout_mapping.addWidget(self.tableWidget_programFiles)

        self.label_symbolFiles = QLabel(self.tab_flash)
        self.label_symbolFiles.setObjectName(u"label_symbolFiles")

        self.verticalLayout_mapping.addWidget(self.label_symbolFiles)

        self.tableWidget_symbolFiles = QTableWidget(self.tab_flash)
        if (self.tableWidget_symbolFiles.columnCount() < 4):
            self.tableWidget_symbolFiles.setColumnCount(4)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.tableWidget_symbolFiles.setHorizontalHeaderItem(0, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.tableWidget_symbolFiles.setHorizontalHeaderItem(1, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.tableWidget_symbolFiles.setHorizontalHeaderItem(2, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.tableWidget_symbolFiles.setHorizontalHeaderItem(3, __qtablewidgetitem7)
        self.tableWidget_symbolFiles.setObjectName(u"tableWidget_symbolFiles")
        self.tableWidget_symbolFiles.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableWidget_symbolFiles.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tableWidget_symbolFiles.horizontalHeader().setStretchLastSection(True)
        self.tableWidget_symbolFiles.verticalHeader().setVisible(False)

        self.verticalLayout_mapping.addWidget(self.tableWidget_symbolFiles)

        self.label_mappingHint = QLabel(self.tab_flash)
        self.label_mappingHint.setObjectName(u"label_mappingHint")

        self.verticalLayout_mapping.addWidget(self.label_mappingHint)


        self.horizontalLayout_flashTab.addLayout(self.verticalLayout_mapping)

        self.tabWidget_main.addTab(self.tab_flash, "")
        self.tab_gitlab = QWidget()
        self.tab_gitlab.setObjectName(u"tab_gitlab")
        self.verticalLayout_gitlabTab = QVBoxLayout(self.tab_gitlab)
        self.verticalLayout_gitlabTab.setObjectName(u"verticalLayout_gitlabTab")
        self.verticalLayout_gitlabTab.setContentsMargins(0, 0, 0, 0)
        self.scrollArea_gitlab = QScrollArea(self.tab_gitlab)
        self.scrollArea_gitlab.setObjectName(u"scrollArea_gitlab")
        self.scrollArea_gitlab.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea_gitlab.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scrollArea_gitlab.setWidgetResizable(True)
        self.scrollAreaWidgetContents_gitlab = QWidget()
        self.scrollAreaWidgetContents_gitlab.setObjectName(u"scrollAreaWidgetContents_gitlab")
        self.verticalLayout_gitlabScroll = QVBoxLayout(self.scrollAreaWidgetContents_gitlab)
        self.verticalLayout_gitlabScroll.setSpacing(12)
        self.verticalLayout_gitlabScroll.setObjectName(u"verticalLayout_gitlabScroll")
        self.verticalLayout_gitlabScroll.setContentsMargins(14, 14, 14, 14)
        self.groupBox_app = QGroupBox(self.scrollAreaWidgetContents_gitlab)
        self.groupBox_app.setObjectName(u"groupBox_app")
        self.gridLayout_app = QGridLayout(self.groupBox_app)
        self.gridLayout_app.setObjectName(u"gridLayout_app")
        self.gridLayout_app.setHorizontalSpacing(8)
        self.gridLayout_app.setVerticalSpacing(6)
        self.label_appProjectCaption = QLabel(self.groupBox_app)
        self.label_appProjectCaption.setObjectName(u"label_appProjectCaption")

        self.gridLayout_app.addWidget(self.label_appProjectCaption, 0, 0, 1, 1)

        self.lineEdit_appProject = QLineEdit(self.groupBox_app)
        self.lineEdit_appProject.setObjectName(u"lineEdit_appProject")

        self.gridLayout_app.addWidget(self.lineEdit_appProject, 0, 1, 1, 2)

        self.label_appRepositoryCaption = QLabel(self.groupBox_app)
        self.label_appRepositoryCaption.setObjectName(u"label_appRepositoryCaption")

        self.gridLayout_app.addWidget(self.label_appRepositoryCaption, 1, 0, 1, 1)

        self.lineEdit_appRepo = QLineEdit(self.groupBox_app)
        self.lineEdit_appRepo.setObjectName(u"lineEdit_appRepo")

        self.gridLayout_app.addWidget(self.lineEdit_appRepo, 1, 1, 1, 1)

        self.pushButton_appBrowse = QPushButton(self.groupBox_app)
        self.pushButton_appBrowse.setObjectName(u"pushButton_appBrowse")

        self.gridLayout_app.addWidget(self.pushButton_appBrowse, 1, 2, 1, 1)

        self.label_appBranchTagCaption = QLabel(self.groupBox_app)
        self.label_appBranchTagCaption.setObjectName(u"label_appBranchTagCaption")

        self.gridLayout_app.addWidget(self.label_appBranchTagCaption, 2, 0, 1, 1)

        self.label_appBranch = QLabel(self.groupBox_app)
        self.label_appBranch.setObjectName(u"label_appBranch")
        self.label_appBranch.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_app.addWidget(self.label_appBranch, 2, 1, 1, 1)

        self.pushButton_appCheckout = QPushButton(self.groupBox_app)
        self.pushButton_appCheckout.setObjectName(u"pushButton_appCheckout")

        self.gridLayout_app.addWidget(self.pushButton_appCheckout, 2, 2, 1, 1)

        self.label_appCommitCaption = QLabel(self.groupBox_app)
        self.label_appCommitCaption.setObjectName(u"label_appCommitCaption")

        self.gridLayout_app.addWidget(self.label_appCommitCaption, 3, 0, 1, 1)

        self.label_appCommit = QLabel(self.groupBox_app)
        self.label_appCommit.setObjectName(u"label_appCommit")
        self.label_appCommit.setWordWrap(True)
        self.label_appCommit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_app.addWidget(self.label_appCommit, 3, 1, 1, 1)

        self.pushButton_appReload = QPushButton(self.groupBox_app)
        self.pushButton_appReload.setObjectName(u"pushButton_appReload")

        self.gridLayout_app.addWidget(self.pushButton_appReload, 3, 2, 1, 1)

        self.label_appBuildCaption = QLabel(self.groupBox_app)
        self.label_appBuildCaption.setObjectName(u"label_appBuildCaption")

        self.gridLayout_app.addWidget(self.label_appBuildCaption, 4, 0, 1, 1)

        self.comboBox_appBuild = QComboBox(self.groupBox_app)
        self.comboBox_appBuild.setObjectName(u"comboBox_appBuild")
        self.comboBox_appBuild.setMinimumSize(QSize(240, 0))

        self.gridLayout_app.addWidget(self.comboBox_appBuild, 4, 1, 1, 1)

        self.label_appFirmwareCaption = QLabel(self.groupBox_app)
        self.label_appFirmwareCaption.setObjectName(u"label_appFirmwareCaption")

        self.gridLayout_app.addWidget(self.label_appFirmwareCaption, 5, 0, 1, 1)

        self.widget_appFirmware = QWidget(self.groupBox_app)
        self.widget_appFirmware.setObjectName(u"widget_appFirmware")
        self.horizontalLayout_appFirmware = QHBoxLayout(self.widget_appFirmware)
        self.horizontalLayout_appFirmware.setSpacing(14)
        self.horizontalLayout_appFirmware.setObjectName(u"horizontalLayout_appFirmware")
        self.horizontalLayout_appFirmware.setContentsMargins(0, 0, 0, 0)
        self.radioButton_appCommit = QRadioButton(self.widget_appFirmware)
        self.radioButton_appCommit.setObjectName(u"radioButton_appCommit")

        self.horizontalLayout_appFirmware.addWidget(self.radioButton_appCommit)

        self.radioButton_appManual = QRadioButton(self.widget_appFirmware)
        self.radioButton_appManual.setObjectName(u"radioButton_appManual")

        self.horizontalLayout_appFirmware.addWidget(self.radioButton_appManual)

        self.pushButton_appChooseJob = QPushButton(self.widget_appFirmware)
        self.pushButton_appChooseJob.setObjectName(u"pushButton_appChooseJob")

        self.horizontalLayout_appFirmware.addWidget(self.pushButton_appChooseJob)

        self.horizontalSpacer_appFirmware = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_appFirmware.addItem(self.horizontalSpacer_appFirmware)


        self.gridLayout_app.addWidget(self.widget_appFirmware, 5, 1, 1, 2)

        self.label_appStatus = QLabel(self.groupBox_app)
        self.label_appStatus.setObjectName(u"label_appStatus")
        self.label_appStatus.setWordWrap(True)
        self.label_appStatus.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_app.addWidget(self.label_appStatus, 6, 1, 1, 2)

        self.gridLayout_app.setColumnStretch(1, 1)

        self.verticalLayout_gitlabScroll.addWidget(self.groupBox_app)

        self.checkBox_advancedDebug = QCheckBox(self.scrollAreaWidgetContents_gitlab)
        self.checkBox_advancedDebug.setObjectName(u"checkBox_advancedDebug")

        self.verticalLayout_gitlabScroll.addWidget(self.checkBox_advancedDebug)

        self.widget_debugParts = QWidget(self.scrollAreaWidgetContents_gitlab)
        self.widget_debugParts.setObjectName(u"widget_debugParts")
        self.horizontalLayout_debugParts = QHBoxLayout(self.widget_debugParts)
        self.horizontalLayout_debugParts.setSpacing(12)
        self.horizontalLayout_debugParts.setObjectName(u"horizontalLayout_debugParts")
        self.horizontalLayout_debugParts.setContentsMargins(0, 0, 0, 0)
        self.groupBox_bm = QGroupBox(self.widget_debugParts)
        self.groupBox_bm.setObjectName(u"groupBox_bm")
        self.gridLayout_bm = QGridLayout(self.groupBox_bm)
        self.gridLayout_bm.setObjectName(u"gridLayout_bm")
        self.gridLayout_bm.setHorizontalSpacing(8)
        self.gridLayout_bm.setVerticalSpacing(6)
        self.label_bmProjectCaption = QLabel(self.groupBox_bm)
        self.label_bmProjectCaption.setObjectName(u"label_bmProjectCaption")

        self.gridLayout_bm.addWidget(self.label_bmProjectCaption, 0, 0, 1, 1)

        self.lineEdit_bmProject = QLineEdit(self.groupBox_bm)
        self.lineEdit_bmProject.setObjectName(u"lineEdit_bmProject")

        self.gridLayout_bm.addWidget(self.lineEdit_bmProject, 0, 1, 1, 2)

        self.label_bmRepositoryCaption = QLabel(self.groupBox_bm)
        self.label_bmRepositoryCaption.setObjectName(u"label_bmRepositoryCaption")

        self.gridLayout_bm.addWidget(self.label_bmRepositoryCaption, 1, 0, 1, 1)

        self.lineEdit_bmRepo = QLineEdit(self.groupBox_bm)
        self.lineEdit_bmRepo.setObjectName(u"lineEdit_bmRepo")

        self.gridLayout_bm.addWidget(self.lineEdit_bmRepo, 1, 1, 1, 1)

        self.pushButton_bmBrowse = QPushButton(self.groupBox_bm)
        self.pushButton_bmBrowse.setObjectName(u"pushButton_bmBrowse")

        self.gridLayout_bm.addWidget(self.pushButton_bmBrowse, 1, 2, 1, 1)

        self.label_bmBranchTagCaption = QLabel(self.groupBox_bm)
        self.label_bmBranchTagCaption.setObjectName(u"label_bmBranchTagCaption")

        self.gridLayout_bm.addWidget(self.label_bmBranchTagCaption, 2, 0, 1, 1)

        self.label_bmBranch = QLabel(self.groupBox_bm)
        self.label_bmBranch.setObjectName(u"label_bmBranch")
        self.label_bmBranch.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_bm.addWidget(self.label_bmBranch, 2, 1, 1, 1)

        self.pushButton_bmCheckout = QPushButton(self.groupBox_bm)
        self.pushButton_bmCheckout.setObjectName(u"pushButton_bmCheckout")

        self.gridLayout_bm.addWidget(self.pushButton_bmCheckout, 2, 2, 1, 1)

        self.label_bmCommitCaption = QLabel(self.groupBox_bm)
        self.label_bmCommitCaption.setObjectName(u"label_bmCommitCaption")

        self.gridLayout_bm.addWidget(self.label_bmCommitCaption, 3, 0, 1, 1)

        self.label_bmCommit = QLabel(self.groupBox_bm)
        self.label_bmCommit.setObjectName(u"label_bmCommit")
        self.label_bmCommit.setWordWrap(True)
        self.label_bmCommit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_bm.addWidget(self.label_bmCommit, 3, 1, 1, 1)

        self.pushButton_bmReload = QPushButton(self.groupBox_bm)
        self.pushButton_bmReload.setObjectName(u"pushButton_bmReload")

        self.gridLayout_bm.addWidget(self.pushButton_bmReload, 3, 2, 1, 1)

        self.label_bmBuildCaption = QLabel(self.groupBox_bm)
        self.label_bmBuildCaption.setObjectName(u"label_bmBuildCaption")

        self.gridLayout_bm.addWidget(self.label_bmBuildCaption, 4, 0, 1, 1)

        self.label_bmBuild = QLabel(self.groupBox_bm)
        self.label_bmBuild.setObjectName(u"label_bmBuild")
        self.label_bmBuild.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_bm.addWidget(self.label_bmBuild, 4, 1, 1, 1)

        self.label_bmFirmwareCaption = QLabel(self.groupBox_bm)
        self.label_bmFirmwareCaption.setObjectName(u"label_bmFirmwareCaption")

        self.gridLayout_bm.addWidget(self.label_bmFirmwareCaption, 5, 0, 1, 1)

        self.widget_bmFirmware = QWidget(self.groupBox_bm)
        self.widget_bmFirmware.setObjectName(u"widget_bmFirmware")
        self.horizontalLayout_bmFirmware = QHBoxLayout(self.widget_bmFirmware)
        self.horizontalLayout_bmFirmware.setSpacing(14)
        self.horizontalLayout_bmFirmware.setObjectName(u"horizontalLayout_bmFirmware")
        self.horizontalLayout_bmFirmware.setContentsMargins(0, 0, 0, 0)
        self.radioButton_bmCommit = QRadioButton(self.widget_bmFirmware)
        self.radioButton_bmCommit.setObjectName(u"radioButton_bmCommit")

        self.horizontalLayout_bmFirmware.addWidget(self.radioButton_bmCommit)

        self.radioButton_bmManual = QRadioButton(self.widget_bmFirmware)
        self.radioButton_bmManual.setObjectName(u"radioButton_bmManual")

        self.horizontalLayout_bmFirmware.addWidget(self.radioButton_bmManual)

        self.pushButton_bmChooseJob = QPushButton(self.widget_bmFirmware)
        self.pushButton_bmChooseJob.setObjectName(u"pushButton_bmChooseJob")

        self.horizontalLayout_bmFirmware.addWidget(self.pushButton_bmChooseJob)

        self.horizontalSpacer_bmFirmware = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_bmFirmware.addItem(self.horizontalSpacer_bmFirmware)


        self.gridLayout_bm.addWidget(self.widget_bmFirmware, 5, 1, 1, 2)

        self.label_bmStatus = QLabel(self.groupBox_bm)
        self.label_bmStatus.setObjectName(u"label_bmStatus")
        self.label_bmStatus.setWordWrap(True)
        self.label_bmStatus.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_bm.addWidget(self.label_bmStatus, 6, 1, 1, 2)

        self.gridLayout_bm.setColumnStretch(1, 1)

        self.horizontalLayout_debugParts.addWidget(self.groupBox_bm)

        self.groupBox_fbl = QGroupBox(self.widget_debugParts)
        self.groupBox_fbl.setObjectName(u"groupBox_fbl")
        self.gridLayout_fbl = QGridLayout(self.groupBox_fbl)
        self.gridLayout_fbl.setObjectName(u"gridLayout_fbl")
        self.gridLayout_fbl.setHorizontalSpacing(8)
        self.gridLayout_fbl.setVerticalSpacing(6)
        self.label_fblProjectCaption = QLabel(self.groupBox_fbl)
        self.label_fblProjectCaption.setObjectName(u"label_fblProjectCaption")

        self.gridLayout_fbl.addWidget(self.label_fblProjectCaption, 0, 0, 1, 1)

        self.lineEdit_fblProject = QLineEdit(self.groupBox_fbl)
        self.lineEdit_fblProject.setObjectName(u"lineEdit_fblProject")

        self.gridLayout_fbl.addWidget(self.lineEdit_fblProject, 0, 1, 1, 2)

        self.label_fblRepositoryCaption = QLabel(self.groupBox_fbl)
        self.label_fblRepositoryCaption.setObjectName(u"label_fblRepositoryCaption")

        self.gridLayout_fbl.addWidget(self.label_fblRepositoryCaption, 1, 0, 1, 1)

        self.lineEdit_fblRepo = QLineEdit(self.groupBox_fbl)
        self.lineEdit_fblRepo.setObjectName(u"lineEdit_fblRepo")

        self.gridLayout_fbl.addWidget(self.lineEdit_fblRepo, 1, 1, 1, 1)

        self.pushButton_fblBrowse = QPushButton(self.groupBox_fbl)
        self.pushButton_fblBrowse.setObjectName(u"pushButton_fblBrowse")

        self.gridLayout_fbl.addWidget(self.pushButton_fblBrowse, 1, 2, 1, 1)

        self.label_fblBranchTagCaption = QLabel(self.groupBox_fbl)
        self.label_fblBranchTagCaption.setObjectName(u"label_fblBranchTagCaption")

        self.gridLayout_fbl.addWidget(self.label_fblBranchTagCaption, 2, 0, 1, 1)

        self.label_fblBranch = QLabel(self.groupBox_fbl)
        self.label_fblBranch.setObjectName(u"label_fblBranch")
        self.label_fblBranch.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_fbl.addWidget(self.label_fblBranch, 2, 1, 1, 1)

        self.pushButton_fblCheckout = QPushButton(self.groupBox_fbl)
        self.pushButton_fblCheckout.setObjectName(u"pushButton_fblCheckout")

        self.gridLayout_fbl.addWidget(self.pushButton_fblCheckout, 2, 2, 1, 1)

        self.label_fblCommitCaption = QLabel(self.groupBox_fbl)
        self.label_fblCommitCaption.setObjectName(u"label_fblCommitCaption")

        self.gridLayout_fbl.addWidget(self.label_fblCommitCaption, 3, 0, 1, 1)

        self.label_fblCommit = QLabel(self.groupBox_fbl)
        self.label_fblCommit.setObjectName(u"label_fblCommit")
        self.label_fblCommit.setWordWrap(True)
        self.label_fblCommit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_fbl.addWidget(self.label_fblCommit, 3, 1, 1, 1)

        self.pushButton_fblReload = QPushButton(self.groupBox_fbl)
        self.pushButton_fblReload.setObjectName(u"pushButton_fblReload")

        self.gridLayout_fbl.addWidget(self.pushButton_fblReload, 3, 2, 1, 1)

        self.label_fblBuildCaption = QLabel(self.groupBox_fbl)
        self.label_fblBuildCaption.setObjectName(u"label_fblBuildCaption")

        self.gridLayout_fbl.addWidget(self.label_fblBuildCaption, 4, 0, 1, 1)

        self.label_fblBuild = QLabel(self.groupBox_fbl)
        self.label_fblBuild.setObjectName(u"label_fblBuild")
        self.label_fblBuild.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_fbl.addWidget(self.label_fblBuild, 4, 1, 1, 1)

        self.label_fblFirmwareCaption = QLabel(self.groupBox_fbl)
        self.label_fblFirmwareCaption.setObjectName(u"label_fblFirmwareCaption")

        self.gridLayout_fbl.addWidget(self.label_fblFirmwareCaption, 5, 0, 1, 1)

        self.widget_fblFirmware = QWidget(self.groupBox_fbl)
        self.widget_fblFirmware.setObjectName(u"widget_fblFirmware")
        self.horizontalLayout_fblFirmware = QHBoxLayout(self.widget_fblFirmware)
        self.horizontalLayout_fblFirmware.setSpacing(14)
        self.horizontalLayout_fblFirmware.setObjectName(u"horizontalLayout_fblFirmware")
        self.horizontalLayout_fblFirmware.setContentsMargins(0, 0, 0, 0)
        self.radioButton_fblCommit = QRadioButton(self.widget_fblFirmware)
        self.radioButton_fblCommit.setObjectName(u"radioButton_fblCommit")

        self.horizontalLayout_fblFirmware.addWidget(self.radioButton_fblCommit)

        self.radioButton_fblManual = QRadioButton(self.widget_fblFirmware)
        self.radioButton_fblManual.setObjectName(u"radioButton_fblManual")

        self.horizontalLayout_fblFirmware.addWidget(self.radioButton_fblManual)

        self.pushButton_fblChooseJob = QPushButton(self.widget_fblFirmware)
        self.pushButton_fblChooseJob.setObjectName(u"pushButton_fblChooseJob")

        self.horizontalLayout_fblFirmware.addWidget(self.pushButton_fblChooseJob)

        self.horizontalSpacer_fblFirmware = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_fblFirmware.addItem(self.horizontalSpacer_fblFirmware)


        self.gridLayout_fbl.addWidget(self.widget_fblFirmware, 5, 1, 1, 2)

        self.label_fblStatus = QLabel(self.groupBox_fbl)
        self.label_fblStatus.setObjectName(u"label_fblStatus")
        self.label_fblStatus.setWordWrap(True)
        self.label_fblStatus.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_fbl.addWidget(self.label_fblStatus, 6, 1, 1, 2)

        self.gridLayout_fbl.setColumnStretch(1, 1)

        self.horizontalLayout_debugParts.addWidget(self.groupBox_fbl)


        self.verticalLayout_gitlabScroll.addWidget(self.widget_debugParts)

        self.verticalSpacer_gitlabTab = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_gitlabScroll.addItem(self.verticalSpacer_gitlabTab)

        self.scrollArea_gitlab.setWidget(self.scrollAreaWidgetContents_gitlab)

        self.verticalLayout_gitlabTab.addWidget(self.scrollArea_gitlab)

        self.tabWidget_main.addTab(self.tab_gitlab, "")
        self.tab_setting = QWidget()
        self.tab_setting.setObjectName(u"tab_setting")
        self.verticalLayout_settingTab = QVBoxLayout(self.tab_setting)
        self.verticalLayout_settingTab.setObjectName(u"verticalLayout_settingTab")
        self.verticalLayout_settingTab.setContentsMargins(0, 0, 0, 0)
        self.scrollArea_setting = QScrollArea(self.tab_setting)
        self.scrollArea_setting.setObjectName(u"scrollArea_setting")
        self.scrollArea_setting.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea_setting.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scrollArea_setting.setWidgetResizable(True)
        self.scrollAreaWidgetContents_setting = QWidget()
        self.scrollAreaWidgetContents_setting.setObjectName(u"scrollAreaWidgetContents_setting")
        self.verticalLayout_settingScroll = QVBoxLayout(self.scrollAreaWidgetContents_setting)
        self.verticalLayout_settingScroll.setSpacing(12)
        self.verticalLayout_settingScroll.setObjectName(u"verticalLayout_settingScroll")
        self.verticalLayout_settingScroll.setContentsMargins(14, 14, 14, 14)
        self.groupBox_profile = QGroupBox(self.scrollAreaWidgetContents_setting)
        self.groupBox_profile.setObjectName(u"groupBox_profile")
        self.gridLayout_profile = QGridLayout(self.groupBox_profile)
        self.gridLayout_profile.setObjectName(u"gridLayout_profile")
        self.gridLayout_profile.setHorizontalSpacing(8)
        self.gridLayout_profile.setVerticalSpacing(6)
        self.label_profile = QLabel(self.groupBox_profile)
        self.label_profile.setObjectName(u"label_profile")

        self.gridLayout_profile.addWidget(self.label_profile, 0, 0, 1, 1)

        self.comboBox_profile = QComboBox(self.groupBox_profile)
        self.comboBox_profile.setObjectName(u"comboBox_profile")
        sizePolicy.setHeightForWidth(self.comboBox_profile.sizePolicy().hasHeightForWidth())
        self.comboBox_profile.setSizePolicy(sizePolicy)

        self.gridLayout_profile.addWidget(self.comboBox_profile, 0, 1, 1, 1)

        self.pushButton_reloadProfiles = QPushButton(self.groupBox_profile)
        self.pushButton_reloadProfiles.setObjectName(u"pushButton_reloadProfiles")

        self.gridLayout_profile.addWidget(self.pushButton_reloadProfiles, 0, 2, 1, 1)

        self.label_profilesDir = QLabel(self.groupBox_profile)
        self.label_profilesDir.setObjectName(u"label_profilesDir")

        self.gridLayout_profile.addWidget(self.label_profilesDir, 1, 0, 1, 1)

        self.lineEdit_profilesDir = QLineEdit(self.groupBox_profile)
        self.lineEdit_profilesDir.setObjectName(u"lineEdit_profilesDir")

        self.gridLayout_profile.addWidget(self.lineEdit_profilesDir, 1, 1, 1, 1)

        self.pushButton_browseProfilesDir = QPushButton(self.groupBox_profile)
        self.pushButton_browseProfilesDir.setObjectName(u"pushButton_browseProfilesDir")

        self.gridLayout_profile.addWidget(self.pushButton_browseProfilesDir, 1, 2, 1, 1)

        self.label_downloadDir = QLabel(self.groupBox_profile)
        self.label_downloadDir.setObjectName(u"label_downloadDir")

        self.gridLayout_profile.addWidget(self.label_downloadDir, 2, 0, 1, 1)

        self.lineEdit_downloadDir = QLineEdit(self.groupBox_profile)
        self.lineEdit_downloadDir.setObjectName(u"lineEdit_downloadDir")

        self.gridLayout_profile.addWidget(self.lineEdit_downloadDir, 2, 1, 1, 1)

        self.pushButton_browseDownloadDir = QPushButton(self.groupBox_profile)
        self.pushButton_browseDownloadDir.setObjectName(u"pushButton_browseDownloadDir")

        self.gridLayout_profile.addWidget(self.pushButton_browseDownloadDir, 2, 2, 1, 1)

        self.label_settingError = QLabel(self.groupBox_profile)
        self.label_settingError.setObjectName(u"label_settingError")
        self.label_settingError.setWordWrap(True)

        self.gridLayout_profile.addWidget(self.label_settingError, 3, 1, 1, 2)

        self.gridLayout_profile.setColumnStretch(1, 1)

        self.verticalLayout_settingScroll.addWidget(self.groupBox_profile)

        self.groupBox_gitlab = QGroupBox(self.scrollAreaWidgetContents_setting)
        self.groupBox_gitlab.setObjectName(u"groupBox_gitlab")
        self.gridLayout_gitlab = QGridLayout(self.groupBox_gitlab)
        self.gridLayout_gitlab.setObjectName(u"gridLayout_gitlab")
        self.gridLayout_gitlab.setHorizontalSpacing(8)
        self.gridLayout_gitlab.setVerticalSpacing(6)
        self.label_gitlabUrl = QLabel(self.groupBox_gitlab)
        self.label_gitlabUrl.setObjectName(u"label_gitlabUrl")

        self.gridLayout_gitlab.addWidget(self.label_gitlabUrl, 0, 0, 1, 1)

        self.lineEdit_gitlabUrl = QLineEdit(self.groupBox_gitlab)
        self.lineEdit_gitlabUrl.setObjectName(u"lineEdit_gitlabUrl")

        self.gridLayout_gitlab.addWidget(self.lineEdit_gitlabUrl, 0, 1, 1, 2)

        self.label_token = QLabel(self.groupBox_gitlab)
        self.label_token.setObjectName(u"label_token")

        self.gridLayout_gitlab.addWidget(self.label_token, 1, 0, 1, 1)

        self.lineEdit_token = QLineEdit(self.groupBox_gitlab)
        self.lineEdit_token.setObjectName(u"lineEdit_token")
        self.lineEdit_token.setEchoMode(QLineEdit.EchoMode.Password)

        self.gridLayout_gitlab.addWidget(self.lineEdit_token, 1, 1, 1, 2)

        self.gridLayout_gitlab.setColumnStretch(1, 1)

        self.verticalLayout_settingScroll.addWidget(self.groupBox_gitlab)

        self.groupBox_winidea = QGroupBox(self.scrollAreaWidgetContents_setting)
        self.groupBox_winidea.setObjectName(u"groupBox_winidea")
        self.gridLayout_winidea = QGridLayout(self.groupBox_winidea)
        self.gridLayout_winidea.setObjectName(u"gridLayout_winidea")
        self.gridLayout_winidea.setHorizontalSpacing(8)
        self.gridLayout_winidea.setVerticalSpacing(6)
        self.label_instance = QLabel(self.groupBox_winidea)
        self.label_instance.setObjectName(u"label_instance")

        self.gridLayout_winidea.addWidget(self.label_instance, 0, 0, 1, 1)

        self.comboBox_instance = QComboBox(self.groupBox_winidea)
        self.comboBox_instance.setObjectName(u"comboBox_instance")
        sizePolicy.setHeightForWidth(self.comboBox_instance.sizePolicy().hasHeightForWidth())
        self.comboBox_instance.setSizePolicy(sizePolicy)

        self.gridLayout_winidea.addWidget(self.comboBox_instance, 0, 1, 1, 1)

        self.pushButton_refreshInstances = QPushButton(self.groupBox_winidea)
        self.pushButton_refreshInstances.setObjectName(u"pushButton_refreshInstances")

        self.gridLayout_winidea.addWidget(self.pushButton_refreshInstances, 0, 2, 1, 1)

        self.label_afterFlash = QLabel(self.groupBox_winidea)
        self.label_afterFlash.setObjectName(u"label_afterFlash")

        self.gridLayout_winidea.addWidget(self.label_afterFlash, 1, 0, 1, 1)

        self.widget_afterFlash = QWidget(self.groupBox_winidea)
        self.widget_afterFlash.setObjectName(u"widget_afterFlash")
        self.horizontalLayout_afterFlash = QHBoxLayout(self.widget_afterFlash)
        self.horizontalLayout_afterFlash.setSpacing(18)
        self.horizontalLayout_afterFlash.setObjectName(u"horizontalLayout_afterFlash")
        self.horizontalLayout_afterFlash.setContentsMargins(0, 0, 0, 0)
        self.checkBox_reset = QCheckBox(self.widget_afterFlash)
        self.checkBox_reset.setObjectName(u"checkBox_reset")
        self.checkBox_reset.setChecked(True)

        self.horizontalLayout_afterFlash.addWidget(self.checkBox_reset)

        self.checkBox_run = QCheckBox(self.widget_afterFlash)
        self.checkBox_run.setObjectName(u"checkBox_run")

        self.horizontalLayout_afterFlash.addWidget(self.checkBox_run)

        self.checkBox_verifyFlash = QCheckBox(self.widget_afterFlash)
        self.checkBox_verifyFlash.setObjectName(u"checkBox_verifyFlash")

        self.horizontalLayout_afterFlash.addWidget(self.checkBox_verifyFlash)

        self.horizontalSpacer_afterFlash = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_afterFlash.addItem(self.horizontalSpacer_afterFlash)


        self.gridLayout_winidea.addWidget(self.widget_afterFlash, 1, 1, 1, 2)

        self.gridLayout_winidea.setColumnStretch(1, 1)

        self.verticalLayout_settingScroll.addWidget(self.groupBox_winidea)

        self.verticalSpacer_settingTab = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_settingScroll.addItem(self.verticalSpacer_settingTab)

        self.scrollArea_setting.setWidget(self.scrollAreaWidgetContents_setting)

        self.verticalLayout_settingTab.addWidget(self.scrollArea_setting)

        self.tabWidget_main.addTab(self.tab_setting, "")

        self.verticalLayout_main.addWidget(self.tabWidget_main)

        self.tabWidget_output = QTabWidget(self.centralWidget_main)
        self.tabWidget_output.setObjectName(u"tabWidget_output")
        self.tab_information = QWidget()
        self.tab_information.setObjectName(u"tab_information")
        self.verticalLayout_information = QVBoxLayout(self.tab_information)
        self.verticalLayout_information.setObjectName(u"verticalLayout_information")
        self.horizontalLayout_logBar = QHBoxLayout()
        self.horizontalLayout_logBar.setObjectName(u"horizontalLayout_logBar")
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

        self.verticalLayout_main.setStretch(4, 5)
        self.verticalLayout_main.setStretch(5, 2)
        MainWindow.setCentralWidget(self.centralWidget_main)
        self.menuBar_main = QMenuBar(MainWindow)
        self.menuBar_main.setObjectName(u"menuBar_main")
        self.menu_file = QMenu(self.menuBar_main)
        self.menu_file.setObjectName(u"menu_file")
        self.menu_view = QMenu(self.menuBar_main)
        self.menu_view.setObjectName(u"menu_view")
        self.menu_tools = QMenu(self.menuBar_main)
        self.menu_tools.setObjectName(u"menu_tools")
        self.menu_help = QMenu(self.menuBar_main)
        self.menu_help.setObjectName(u"menu_help")
        MainWindow.setMenuBar(self.menuBar_main)
        self.statusBar_main = QStatusBar(MainWindow)
        self.statusBar_main.setObjectName(u"statusBar_main")
        MainWindow.setStatusBar(self.statusBar_main)
#if QT_CONFIG(shortcut)
        self.label_firmwareSource.setBuddy(self.pushButton_loadFromGitlab)
#endif // QT_CONFIG(shortcut)

        self.menuBar_main.addAction(self.menu_file.menuAction())
        self.menuBar_main.addAction(self.menu_view.menuAction())
        self.menuBar_main.addAction(self.menu_tools.menuAction())
        self.menuBar_main.addAction(self.menu_help.menuAction())
        self.menu_file.addAction(self.action_exportBundle)
        self.menu_file.addAction(self.action_openHistory)
        self.menu_file.addAction(self.action_openLogFolder)
        self.menu_file.addAction(self.action_openDownloadFolder)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.action_exit)
        self.menu_view.addAction(self.action_darkMode)
        self.menu_view.addSeparator()
        self.menu_view.addAction(self.action_tabFlash)
        self.menu_view.addAction(self.action_tabGitlab)
        self.menu_view.addAction(self.action_tabSetting)
        self.menu_tools.addAction(self.action_testGitlab)
        self.menu_tools.addAction(self.action_checkCores)
        self.menu_tools.addSeparator()
        self.menu_tools.addAction(self.action_refreshInstances)
        self.menu_help.addAction(self.action_userGuide)
        self.menu_help.addAction(self.action_about)

        self.retranslateUi(MainWindow)

        self.tabWidget_main.setCurrentIndex(0)
        self.tabWidget_output.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"WFlash", None))
        self.action_exportBundle.setText(QCoreApplication.translate("MainWindow", u"Export debug bundle\u2026", None))
#if QT_CONFIG(shortcut)
        self.action_exportBundle.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+E", None))
#endif // QT_CONFIG(shortcut)
        self.action_openHistory.setText(QCoreApplication.translate("MainWindow", u"Open flash history", None))
        self.action_openLogFolder.setText(QCoreApplication.translate("MainWindow", u"Open log folder", None))
        self.action_openDownloadFolder.setText(QCoreApplication.translate("MainWindow", u"Open download folder", None))
        self.action_exit.setText(QCoreApplication.translate("MainWindow", u"Exit", None))
#if QT_CONFIG(shortcut)
        self.action_exit.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+Q", None))
#endif // QT_CONFIG(shortcut)
        self.action_darkMode.setText(QCoreApplication.translate("MainWindow", u"Dark mode", None))
        self.action_tabFlash.setText(QCoreApplication.translate("MainWindow", u"Flash", None))
#if QT_CONFIG(shortcut)
        self.action_tabFlash.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+1", None))
#endif // QT_CONFIG(shortcut)
        self.action_tabGitlab.setText(QCoreApplication.translate("MainWindow", u"GitLab", None))
#if QT_CONFIG(shortcut)
        self.action_tabGitlab.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+2", None))
#endif // QT_CONFIG(shortcut)
        self.action_tabSetting.setText(QCoreApplication.translate("MainWindow", u"Setting", None))
#if QT_CONFIG(shortcut)
        self.action_tabSetting.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+3", None))
#endif // QT_CONFIG(shortcut)
        self.action_testGitlab.setText(QCoreApplication.translate("MainWindow", u"Test GitLab connection", None))
        self.action_checkCores.setText(QCoreApplication.translate("MainWindow", u"Check winIDEA cores", None))
        self.action_refreshInstances.setText(QCoreApplication.translate("MainWindow", u"Refresh winIDEA instances", None))
#if QT_CONFIG(shortcut)
        self.action_refreshInstances.setShortcut(QCoreApplication.translate("MainWindow", u"F5", None))
#endif // QT_CONFIG(shortcut)
        self.action_userGuide.setText(QCoreApplication.translate("MainWindow", u"User Guide", None))
#if QT_CONFIG(shortcut)
        self.action_userGuide.setShortcut(QCoreApplication.translate("MainWindow", u"F1", None))
#endif // QT_CONFIG(shortcut)
        self.action_about.setText(QCoreApplication.translate("MainWindow", u"About WFlash", None))
        self.pushButton_flash.setText(QCoreApplication.translate("MainWindow", u"Flash", None))
        self.pushButton_flash.setProperty(u"state", QCoreApplication.translate("MainWindow", u"idle", None))
        self.label_flashStats.setText(QCoreApplication.translate("MainWindow", u"ETA: -- | Speed: --", None))
        self.label_step.setText(QCoreApplication.translate("MainWindow", u"Step: Idle", None))
        self.label_rollbackWarning.setText(QCoreApplication.translate("MainWindow", u"ROLLBACK FAILED \u2014 the winIDEA workspace may still point to the new files. Check the download and symbol file list in winIDEA before flashing again.", None))
        self.label_summaryHeader.setText(QCoreApplication.translate("MainWindow", u"Firmware to flash", None))
        self.label_summaryApp.setText("")
        self.label_summaryBm.setText("")
        self.label_summaryFbl.setText("")
        self.label_summaryAdvanced.setText(QCoreApplication.translate("MainWindow", u"Advanced Debug: off", None))
        self.label_firmwareSource.setText(QCoreApplication.translate("MainWindow", u"Firmware source", None))
        self.pushButton_loadFromGitlab.setText(QCoreApplication.translate("MainWindow", u"Load from GitLab\u2026", None))
        self.label_sourceTitle.setText(QCoreApplication.translate("MainWindow", u"No firmware loaded \u2014 use Load from GitLab\u2026", None))
        self.label_sourceDetail.setText("")
        self.label_sourceCache.setText("")
        self.label_programFiles.setText(QCoreApplication.translate("MainWindow", u"Program Files", None))
        ___qtablewidgetitem = self.tableWidget_programFiles.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"#", None))
        ___qtablewidgetitem1 = self.tableWidget_programFiles.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"Source", None))
        ___qtablewidgetitem2 = self.tableWidget_programFiles.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindow", u"File", None))
        ___qtablewidgetitem3 = self.tableWidget_programFiles.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindow", u"Offset", None))
        self.label_symbolFiles.setText(QCoreApplication.translate("MainWindow", u"Symbol Files", None))
        ___qtablewidgetitem4 = self.tableWidget_symbolFiles.horizontalHeaderItem(0)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("MainWindow", u"#", None))
        ___qtablewidgetitem5 = self.tableWidget_symbolFiles.horizontalHeaderItem(1)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("MainWindow", u"Source", None))
        ___qtablewidgetitem6 = self.tableWidget_symbolFiles.horizontalHeaderItem(2)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("MainWindow", u"File", None))
        self.label_mappingHint.setText(QCoreApplication.translate("MainWindow", u"Load firmware to fill the mapping.", None))
        self.tabWidget_main.setTabText(self.tabWidget_main.indexOf(self.tab_flash), QCoreApplication.translate("MainWindow", u"Flash", None))
        self.groupBox_app.setTitle(QCoreApplication.translate("MainWindow", u"App", None))
        self.label_appProjectCaption.setText(QCoreApplication.translate("MainWindow", u"Project", None))
        self.label_appRepositoryCaption.setText(QCoreApplication.translate("MainWindow", u"Repository", None))
        self.pushButton_appBrowse.setText(QCoreApplication.translate("MainWindow", u"Browse", None))
        self.label_appBranchTagCaption.setText(QCoreApplication.translate("MainWindow", u"Branch/Tag", None))
        self.label_appBranch.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.pushButton_appCheckout.setText(QCoreApplication.translate("MainWindow", u"Checkout", None))
        self.label_appCommitCaption.setText(QCoreApplication.translate("MainWindow", u"Commit", None))
        self.label_appCommit.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.pushButton_appReload.setText(QCoreApplication.translate("MainWindow", u"Reload", None))
#if QT_CONFIG(tooltip)
        self.pushButton_appReload.setToolTip(QCoreApplication.translate("MainWindow", u"Read the repository again: branch, commit and local changes", None))
#endif // QT_CONFIG(tooltip)
        self.label_appBuildCaption.setText(QCoreApplication.translate("MainWindow", u"Build", None))
        self.label_appFirmwareCaption.setText(QCoreApplication.translate("MainWindow", u"Firmware", None))
        self.radioButton_appCommit.setText(QCoreApplication.translate("MainWindow", u"From checked-out commit", None))
        self.radioButton_appManual.setText(QCoreApplication.translate("MainWindow", u"Manual", None))
        self.pushButton_appChooseJob.setText(QCoreApplication.translate("MainWindow", u"Choose Job", None))
        self.label_appStatus.setText("")
        self.checkBox_advancedDebug.setText(QCoreApplication.translate("MainWindow", u"Advanced Debug", None))
        self.groupBox_bm.setTitle(QCoreApplication.translate("MainWindow", u"Boot Manager", None))
        self.label_bmProjectCaption.setText(QCoreApplication.translate("MainWindow", u"Project", None))
        self.label_bmRepositoryCaption.setText(QCoreApplication.translate("MainWindow", u"Repository", None))
        self.lineEdit_bmRepo.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Optional", None))
        self.pushButton_bmBrowse.setText(QCoreApplication.translate("MainWindow", u"Browse", None))
        self.label_bmBranchTagCaption.setText(QCoreApplication.translate("MainWindow", u"Branch/Tag", None))
        self.label_bmBranch.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.pushButton_bmCheckout.setText(QCoreApplication.translate("MainWindow", u"Checkout", None))
        self.label_bmCommitCaption.setText(QCoreApplication.translate("MainWindow", u"Commit", None))
        self.label_bmCommit.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.pushButton_bmReload.setText(QCoreApplication.translate("MainWindow", u"Reload", None))
#if QT_CONFIG(tooltip)
        self.pushButton_bmReload.setToolTip(QCoreApplication.translate("MainWindow", u"Read the repository again: branch, commit and local changes", None))
#endif // QT_CONFIG(tooltip)
        self.label_bmBuildCaption.setText(QCoreApplication.translate("MainWindow", u"Build", None))
        self.label_bmBuild.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.label_bmFirmwareCaption.setText(QCoreApplication.translate("MainWindow", u"Firmware", None))
        self.radioButton_bmCommit.setText(QCoreApplication.translate("MainWindow", u"From checked-out commit", None))
        self.radioButton_bmManual.setText(QCoreApplication.translate("MainWindow", u"Manual", None))
        self.pushButton_bmChooseJob.setText(QCoreApplication.translate("MainWindow", u"Choose Job", None))
        self.label_bmStatus.setText("")
        self.groupBox_fbl.setTitle(QCoreApplication.translate("MainWindow", u"Flash Bootloader", None))
        self.label_fblProjectCaption.setText(QCoreApplication.translate("MainWindow", u"Project", None))
        self.label_fblRepositoryCaption.setText(QCoreApplication.translate("MainWindow", u"Repository", None))
        self.lineEdit_fblRepo.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Optional", None))
        self.pushButton_fblBrowse.setText(QCoreApplication.translate("MainWindow", u"Browse", None))
        self.label_fblBranchTagCaption.setText(QCoreApplication.translate("MainWindow", u"Branch/Tag", None))
        self.label_fblBranch.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.pushButton_fblCheckout.setText(QCoreApplication.translate("MainWindow", u"Checkout", None))
        self.label_fblCommitCaption.setText(QCoreApplication.translate("MainWindow", u"Commit", None))
        self.label_fblCommit.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.pushButton_fblReload.setText(QCoreApplication.translate("MainWindow", u"Reload", None))
#if QT_CONFIG(tooltip)
        self.pushButton_fblReload.setToolTip(QCoreApplication.translate("MainWindow", u"Read the repository again: branch, commit and local changes", None))
#endif // QT_CONFIG(tooltip)
        self.label_fblBuildCaption.setText(QCoreApplication.translate("MainWindow", u"Build", None))
        self.label_fblBuild.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.label_fblFirmwareCaption.setText(QCoreApplication.translate("MainWindow", u"Firmware", None))
        self.radioButton_fblCommit.setText(QCoreApplication.translate("MainWindow", u"From checked-out commit", None))
        self.radioButton_fblManual.setText(QCoreApplication.translate("MainWindow", u"Manual", None))
        self.pushButton_fblChooseJob.setText(QCoreApplication.translate("MainWindow", u"Choose Job", None))
        self.label_fblStatus.setText("")
        self.tabWidget_main.setTabText(self.tabWidget_main.indexOf(self.tab_gitlab), QCoreApplication.translate("MainWindow", u"GitLab", None))
        self.groupBox_profile.setTitle(QCoreApplication.translate("MainWindow", u"Profile", None))
        self.label_profile.setText(QCoreApplication.translate("MainWindow", u"Profile", None))
        self.pushButton_reloadProfiles.setText(QCoreApplication.translate("MainWindow", u"Reload", None))
        self.label_profilesDir.setText(QCoreApplication.translate("MainWindow", u"Profiles folder", None))
        self.pushButton_browseProfilesDir.setText(QCoreApplication.translate("MainWindow", u"Browse\u2026", None))
        self.label_downloadDir.setText(QCoreApplication.translate("MainWindow", u"Download folder", None))
        self.pushButton_browseDownloadDir.setText(QCoreApplication.translate("MainWindow", u"Browse\u2026", None))
        self.label_settingError.setText("")
        self.groupBox_gitlab.setTitle(QCoreApplication.translate("MainWindow", u"GitLab connection", None))
        self.label_gitlabUrl.setText(QCoreApplication.translate("MainWindow", u"GitLab URL", None))
        self.lineEdit_gitlabUrl.setPlaceholderText(QCoreApplication.translate("MainWindow", u"https://gitlab.example.com/group", None))
        self.label_token.setText(QCoreApplication.translate("MainWindow", u"Access token", None))
        self.lineEdit_token.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Personal Access Token (scope read_api)", None))
        self.groupBox_winidea.setTitle(QCoreApplication.translate("MainWindow", u"winIDEA", None))
        self.label_instance.setText(QCoreApplication.translate("MainWindow", u"Instance", None))
        self.pushButton_refreshInstances.setText(QCoreApplication.translate("MainWindow", u"Refresh", None))
        self.label_afterFlash.setText(QCoreApplication.translate("MainWindow", u"After flash", None))
        self.checkBox_reset.setText(QCoreApplication.translate("MainWindow", u"Reset target", None))
        self.checkBox_run.setText(QCoreApplication.translate("MainWindow", u"Run after reset", None))
        self.checkBox_verifyFlash.setText(QCoreApplication.translate("MainWindow", u"Verify samples", None))
#if QT_CONFIG(tooltip)
        self.checkBox_verifyFlash.setToolTip(QCoreApplication.translate("MainWindow", u"Read samples of the flash back and compare them with the files. Adds about 3 minutes.", None))
#endif // QT_CONFIG(tooltip)
        self.tabWidget_main.setTabText(self.tabWidget_main.indexOf(self.tab_setting), QCoreApplication.translate("MainWindow", u"Setting", None))
        self.pushButton_copyLog.setText(QCoreApplication.translate("MainWindow", u"Copy", None))
        self.pushButton_clearLog.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.pushButton_exportBundle.setText(QCoreApplication.translate("MainWindow", u"Export debug bundle\u2026", None))
        self.tabWidget_output.setTabText(self.tabWidget_output.indexOf(self.tab_information), QCoreApplication.translate("MainWindow", u"Information", None))
        self.menu_file.setTitle(QCoreApplication.translate("MainWindow", u"&File", None))
        self.menu_view.setTitle(QCoreApplication.translate("MainWindow", u"&View", None))
        self.menu_tools.setTitle(QCoreApplication.translate("MainWindow", u"&Tools", None))
        self.menu_help.setTitle(QCoreApplication.translate("MainWindow", u"&Help", None))
    # retranslateUi


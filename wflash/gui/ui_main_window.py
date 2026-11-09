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
    QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSpacerItem, QStatusBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

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
        self.frame_developer = QFrame(self.scrollAreaWidgetContents_flashPanel)
        self.frame_developer.setObjectName(u"frame_developer")
        self.frame_developer.setFrameShape(QFrame.Shape.NoFrame)
        self.verticalLayout_developer = QVBoxLayout(self.frame_developer)
        self.verticalLayout_developer.setSpacing(8)
        self.verticalLayout_developer.setObjectName(u"verticalLayout_developer")
        self.verticalLayout_developer.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_repoState = QVBoxLayout()
        self.verticalLayout_repoState.setSpacing(1)
        self.verticalLayout_repoState.setObjectName(u"verticalLayout_repoState")
        self.label_repoBranch = QLabel(self.frame_developer)
        self.label_repoBranch.setObjectName(u"label_repoBranch")

        self.verticalLayout_repoState.addWidget(self.label_repoBranch)

        self.label_repoCommit = QLabel(self.frame_developer)
        self.label_repoCommit.setObjectName(u"label_repoCommit")

        self.verticalLayout_repoState.addWidget(self.label_repoCommit)

        self.label_repoChanges = QLabel(self.frame_developer)
        self.label_repoChanges.setObjectName(u"label_repoChanges")
        self.label_repoChanges.setWordWrap(True)

        self.verticalLayout_repoState.addWidget(self.label_repoChanges)

        self.label_repoFlashHint = QLabel(self.frame_developer)
        self.label_repoFlashHint.setObjectName(u"label_repoFlashHint")
        self.label_repoFlashHint.setWordWrap(True)

        self.verticalLayout_repoState.addWidget(self.label_repoFlashHint)


        self.verticalLayout_developer.addLayout(self.verticalLayout_repoState)

        self.frame_application = QFrame(self.frame_developer)
        self.frame_application.setObjectName(u"frame_application")
        self.frame_application.setFrameShape(QFrame.Shape.StyledPanel)
        self.verticalLayout_application = QVBoxLayout(self.frame_application)
        self.verticalLayout_application.setSpacing(6)
        self.verticalLayout_application.setObjectName(u"verticalLayout_application")
        self.verticalLayout_application.setContentsMargins(8, 8, 8, 8)
        self.label_applicationHeader = QLabel(self.frame_application)
        self.label_applicationHeader.setObjectName(u"label_applicationHeader")

        self.verticalLayout_application.addWidget(self.label_applicationHeader)

        self.horizontalLayout_build = QHBoxLayout()
        self.horizontalLayout_build.setObjectName(u"horizontalLayout_build")
        self.label_build = QLabel(self.frame_application)
        self.label_build.setObjectName(u"label_build")

        self.horizontalLayout_build.addWidget(self.label_build)

        self.comboBox_build = QComboBox(self.frame_application)
        self.comboBox_build.setObjectName(u"comboBox_build")
        sizePolicy.setHeightForWidth(self.comboBox_build.sizePolicy().hasHeightForWidth())
        self.comboBox_build.setSizePolicy(sizePolicy)

        self.horizontalLayout_build.addWidget(self.comboBox_build)


        self.verticalLayout_application.addLayout(self.horizontalLayout_build)

        self.pushButton_loadBuild = QPushButton(self.frame_application)
        self.pushButton_loadBuild.setObjectName(u"pushButton_loadBuild")

        self.verticalLayout_application.addWidget(self.pushButton_loadBuild)

        self.label_loadStatus = QLabel(self.frame_application)
        self.label_loadStatus.setObjectName(u"label_loadStatus")
        self.label_loadStatus.setWordWrap(True)

        self.verticalLayout_application.addWidget(self.label_loadStatus)

        self.horizontalLayout_chooseJob = QHBoxLayout()
        self.horizontalLayout_chooseJob.setObjectName(u"horizontalLayout_chooseJob")
        self.pushButton_chooseJob = QPushButton(self.frame_application)
        self.pushButton_chooseJob.setObjectName(u"pushButton_chooseJob")

        self.horizontalLayout_chooseJob.addWidget(self.pushButton_chooseJob)

        self.horizontalSpacer_chooseJob = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_chooseJob.addItem(self.horizontalSpacer_chooseJob)


        self.verticalLayout_application.addLayout(self.horizontalLayout_chooseJob)


        self.verticalLayout_developer.addWidget(self.frame_application)

        self.frame_advancedDebug = QFrame(self.frame_developer)
        self.frame_advancedDebug.setObjectName(u"frame_advancedDebug")
        self.frame_advancedDebug.setFrameShape(QFrame.Shape.StyledPanel)
        self.verticalLayout_advancedDebug = QVBoxLayout(self.frame_advancedDebug)
        self.verticalLayout_advancedDebug.setSpacing(6)
        self.verticalLayout_advancedDebug.setObjectName(u"verticalLayout_advancedDebug")
        self.verticalLayout_advancedDebug.setContentsMargins(8, 8, 8, 8)
        self.checkBox_advancedDebug = QCheckBox(self.frame_advancedDebug)
        self.checkBox_advancedDebug.setObjectName(u"checkBox_advancedDebug")

        self.verticalLayout_advancedDebug.addWidget(self.checkBox_advancedDebug)

        self.gridLayout_advancedDebug = QGridLayout()
        self.gridLayout_advancedDebug.setObjectName(u"gridLayout_advancedDebug")
        self.gridLayout_advancedDebug.setContentsMargins(0, 0, 0, 0)
        self.label_bmName = QLabel(self.frame_advancedDebug)
        self.label_bmName.setObjectName(u"label_bmName")

        self.gridLayout_advancedDebug.addWidget(self.label_bmName, 0, 0, 1, 1)

        self.label_bmSource = QLabel(self.frame_advancedDebug)
        self.label_bmSource.setObjectName(u"label_bmSource")
        self.label_bmSource.setWordWrap(True)

        self.gridLayout_advancedDebug.addWidget(self.label_bmSource, 0, 1, 1, 1)

        self.pushButton_loadBm = QPushButton(self.frame_advancedDebug)
        self.pushButton_loadBm.setObjectName(u"pushButton_loadBm")

        self.gridLayout_advancedDebug.addWidget(self.pushButton_loadBm, 0, 2, 1, 1)

        self.label_fblName = QLabel(self.frame_advancedDebug)
        self.label_fblName.setObjectName(u"label_fblName")

        self.gridLayout_advancedDebug.addWidget(self.label_fblName, 1, 0, 1, 1)

        self.label_fblSource = QLabel(self.frame_advancedDebug)
        self.label_fblSource.setObjectName(u"label_fblSource")
        self.label_fblSource.setWordWrap(True)

        self.gridLayout_advancedDebug.addWidget(self.label_fblSource, 1, 1, 1, 1)

        self.pushButton_loadFbl = QPushButton(self.frame_advancedDebug)
        self.pushButton_loadFbl.setObjectName(u"pushButton_loadFbl")

        self.gridLayout_advancedDebug.addWidget(self.pushButton_loadFbl, 1, 2, 1, 1)


        self.verticalLayout_advancedDebug.addLayout(self.gridLayout_advancedDebug)


        self.verticalLayout_developer.addWidget(self.frame_advancedDebug)


        self.verticalLayout_flashScroll.addWidget(self.frame_developer)

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
        self.groupBox_firmware = QGroupBox(self.scrollAreaWidgetContents_setting)
        self.groupBox_firmware.setObjectName(u"groupBox_firmware")
        self.groupBox_firmware.setMaximumSize(QSize(760, 16777215))
        self.gridLayout_firmware = QGridLayout(self.groupBox_firmware)
        self.gridLayout_firmware.setObjectName(u"gridLayout_firmware")
        self.gridLayout_firmware.setHorizontalSpacing(8)
        self.gridLayout_firmware.setVerticalSpacing(8)
        self.label_profile = QLabel(self.groupBox_firmware)
        self.label_profile.setObjectName(u"label_profile")

        self.gridLayout_firmware.addWidget(self.label_profile, 0, 0, 1, 1)

        self.horizontalLayout_profile = QHBoxLayout()
        self.horizontalLayout_profile.setObjectName(u"horizontalLayout_profile")
        self.comboBox_profile = QComboBox(self.groupBox_firmware)
        self.comboBox_profile.setObjectName(u"comboBox_profile")
        sizePolicy.setHeightForWidth(self.comboBox_profile.sizePolicy().hasHeightForWidth())
        self.comboBox_profile.setSizePolicy(sizePolicy)

        self.horizontalLayout_profile.addWidget(self.comboBox_profile)

        self.pushButton_reloadProfiles = QPushButton(self.groupBox_firmware)
        self.pushButton_reloadProfiles.setObjectName(u"pushButton_reloadProfiles")

        self.horizontalLayout_profile.addWidget(self.pushButton_reloadProfiles)


        self.gridLayout_firmware.addLayout(self.horizontalLayout_profile, 0, 1, 1, 1)

        self.frame_sourceRepoSetting = QFrame(self.groupBox_firmware)
        self.frame_sourceRepoSetting.setObjectName(u"frame_sourceRepoSetting")
        self.frame_sourceRepoSetting.setFrameShape(QFrame.Shape.NoFrame)
        self.gridLayout_sourceRepo = QGridLayout(self.frame_sourceRepoSetting)
        self.gridLayout_sourceRepo.setObjectName(u"gridLayout_sourceRepo")
        self.gridLayout_sourceRepo.setHorizontalSpacing(6)
        self.gridLayout_sourceRepo.setVerticalSpacing(6)
        self.gridLayout_sourceRepo.setContentsMargins(0, 0, 0, 0)
        self.label_sourceRepo = QLabel(self.frame_sourceRepoSetting)
        self.label_sourceRepo.setObjectName(u"label_sourceRepo")

        self.gridLayout_sourceRepo.addWidget(self.label_sourceRepo, 0, 0, 1, 1)

        self.lineEdit_sourceRepo = QLineEdit(self.frame_sourceRepoSetting)
        self.lineEdit_sourceRepo.setObjectName(u"lineEdit_sourceRepo")

        self.gridLayout_sourceRepo.addWidget(self.lineEdit_sourceRepo, 0, 1, 1, 1)

        self.pushButton_browseRepo = QPushButton(self.frame_sourceRepoSetting)
        self.pushButton_browseRepo.setObjectName(u"pushButton_browseRepo")

        self.gridLayout_sourceRepo.addWidget(self.pushButton_browseRepo, 0, 2, 1, 1)

        self.pushButton_reloadRepo = QPushButton(self.frame_sourceRepoSetting)
        self.pushButton_reloadRepo.setObjectName(u"pushButton_reloadRepo")

        self.gridLayout_sourceRepo.addWidget(self.pushButton_reloadRepo, 0, 3, 1, 1)

        self.horizontalLayout_repoSetting = QHBoxLayout()
        self.horizontalLayout_repoSetting.setObjectName(u"horizontalLayout_repoSetting")
        self.label_repoSummary = QLabel(self.frame_sourceRepoSetting)
        self.label_repoSummary.setObjectName(u"label_repoSummary")
        self.label_repoSummary.setWordWrap(True)

        self.horizontalLayout_repoSetting.addWidget(self.label_repoSummary)

        self.pushButton_checkout = QPushButton(self.frame_sourceRepoSetting)
        self.pushButton_checkout.setObjectName(u"pushButton_checkout")

        self.horizontalLayout_repoSetting.addWidget(self.pushButton_checkout)

        self.horizontalLayout_repoSetting.setStretch(0, 1)

        self.gridLayout_sourceRepo.addLayout(self.horizontalLayout_repoSetting, 1, 1, 1, 3)

        self.label_repoAutoHint = QLabel(self.frame_sourceRepoSetting)
        self.label_repoAutoHint.setObjectName(u"label_repoAutoHint")
        self.label_repoAutoHint.setWordWrap(True)

        self.gridLayout_sourceRepo.addWidget(self.label_repoAutoHint, 2, 1, 1, 3)


        self.gridLayout_firmware.addWidget(self.frame_sourceRepoSetting, 1, 0, 1, 2)


        self.verticalLayout_settingScroll.addWidget(self.groupBox_firmware)

        self.groupBox_winidea = QGroupBox(self.scrollAreaWidgetContents_setting)
        self.groupBox_winidea.setObjectName(u"groupBox_winidea")
        self.groupBox_winidea.setMaximumSize(QSize(760, 16777215))
        self.gridLayout_winidea = QGridLayout(self.groupBox_winidea)
        self.gridLayout_winidea.setObjectName(u"gridLayout_winidea")
        self.gridLayout_winidea.setHorizontalSpacing(8)
        self.label_instance = QLabel(self.groupBox_winidea)
        self.label_instance.setObjectName(u"label_instance")

        self.gridLayout_winidea.addWidget(self.label_instance, 0, 0, 1, 1)

        self.horizontalLayout_instance = QHBoxLayout()
        self.horizontalLayout_instance.setObjectName(u"horizontalLayout_instance")
        self.comboBox_instance = QComboBox(self.groupBox_winidea)
        self.comboBox_instance.setObjectName(u"comboBox_instance")
        sizePolicy.setHeightForWidth(self.comboBox_instance.sizePolicy().hasHeightForWidth())
        self.comboBox_instance.setSizePolicy(sizePolicy)

        self.horizontalLayout_instance.addWidget(self.comboBox_instance)

        self.pushButton_refreshInstances = QPushButton(self.groupBox_winidea)
        self.pushButton_refreshInstances.setObjectName(u"pushButton_refreshInstances")

        self.horizontalLayout_instance.addWidget(self.pushButton_refreshInstances)


        self.gridLayout_winidea.addLayout(self.horizontalLayout_instance, 0, 1, 1, 1)


        self.verticalLayout_settingScroll.addWidget(self.groupBox_winidea)

        self.groupBox_afterFlash = QGroupBox(self.scrollAreaWidgetContents_setting)
        self.groupBox_afterFlash.setObjectName(u"groupBox_afterFlash")
        self.groupBox_afterFlash.setMaximumSize(QSize(760, 16777215))
        self.verticalLayout_afterFlash = QVBoxLayout(self.groupBox_afterFlash)
        self.verticalLayout_afterFlash.setSpacing(6)
        self.verticalLayout_afterFlash.setObjectName(u"verticalLayout_afterFlash")
        self.horizontalLayout_afterFlash = QHBoxLayout()
        self.horizontalLayout_afterFlash.setObjectName(u"horizontalLayout_afterFlash")
        self.checkBox_reset = QCheckBox(self.groupBox_afterFlash)
        self.checkBox_reset.setObjectName(u"checkBox_reset")
        self.checkBox_reset.setChecked(True)

        self.horizontalLayout_afterFlash.addWidget(self.checkBox_reset)

        self.checkBox_run = QCheckBox(self.groupBox_afterFlash)
        self.checkBox_run.setObjectName(u"checkBox_run")

        self.horizontalLayout_afterFlash.addWidget(self.checkBox_run)

        self.checkBox_verifyFlash = QCheckBox(self.groupBox_afterFlash)
        self.checkBox_verifyFlash.setObjectName(u"checkBox_verifyFlash")

        self.horizontalLayout_afterFlash.addWidget(self.checkBox_verifyFlash)

        self.horizontalSpacer_afterFlash = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_afterFlash.addItem(self.horizontalSpacer_afterFlash)


        self.verticalLayout_afterFlash.addLayout(self.horizontalLayout_afterFlash)

        self.label_verifyHint = QLabel(self.groupBox_afterFlash)
        self.label_verifyHint.setObjectName(u"label_verifyHint")
        self.label_verifyHint.setWordWrap(True)

        self.verticalLayout_afterFlash.addWidget(self.label_verifyHint)


        self.verticalLayout_settingScroll.addWidget(self.groupBox_afterFlash)

        self.widget_preferencesRow = QWidget(self.scrollAreaWidgetContents_setting)
        self.widget_preferencesRow.setObjectName(u"widget_preferencesRow")
        self.widget_preferencesRow.setMaximumSize(QSize(760, 16777215))
        self.horizontalLayout_preferences = QHBoxLayout(self.widget_preferencesRow)
        self.horizontalLayout_preferences.setObjectName(u"horizontalLayout_preferences")
        self.horizontalLayout_preferences.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_preferences = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_preferences.addItem(self.horizontalSpacer_preferences)

        self.pushButton_preferences = QPushButton(self.widget_preferencesRow)
        self.pushButton_preferences.setObjectName(u"pushButton_preferences")

        self.horizontalLayout_preferences.addWidget(self.pushButton_preferences)


        self.verticalLayout_settingScroll.addWidget(self.widget_preferencesRow)

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
        self.statusBar_main = QStatusBar(MainWindow)
        self.statusBar_main.setObjectName(u"statusBar_main")
        MainWindow.setStatusBar(self.statusBar_main)
#if QT_CONFIG(shortcut)
        self.label_build.setBuddy(self.comboBox_build)
        self.label_firmwareSource.setBuddy(self.pushButton_loadFromGitlab)
        self.label_profile.setBuddy(self.comboBox_profile)
        self.label_sourceRepo.setBuddy(self.lineEdit_sourceRepo)
        self.label_instance.setBuddy(self.comboBox_instance)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(MainWindow)

        self.tabWidget_main.setCurrentIndex(0)
        self.tabWidget_output.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"WFlash", None))
        self.pushButton_flash.setText(QCoreApplication.translate("MainWindow", u"Flash", None))
        self.pushButton_flash.setProperty(u"state", QCoreApplication.translate("MainWindow", u"idle", None))
        self.label_flashStats.setText(QCoreApplication.translate("MainWindow", u"ETA: -- | Speed: --", None))
        self.label_step.setText(QCoreApplication.translate("MainWindow", u"Step: Idle", None))
        self.label_rollbackWarning.setText(QCoreApplication.translate("MainWindow", u"ROLLBACK FAILED \u2014 the winIDEA workspace may still point to the new files. Check the download and symbol file list in winIDEA before flashing again.", None))
        self.label_repoBranch.setText(QCoreApplication.translate("MainWindow", u"Branch: -", None))
        self.label_repoCommit.setText(QCoreApplication.translate("MainWindow", u"Commit: -", None))
        self.label_repoChanges.setText("")
        self.label_repoFlashHint.setText(QCoreApplication.translate("MainWindow", u"Updated when you come back to WFlash. Change the repo or branch in Setting.", None))
        self.label_applicationHeader.setText(QCoreApplication.translate("MainWindow", u"Application", None))
        self.label_build.setText(QCoreApplication.translate("MainWindow", u"Build", None))
        self.pushButton_loadBuild.setText(QCoreApplication.translate("MainWindow", u"Load firmware for this commit", None))
        self.label_loadStatus.setText("")
        self.pushButton_chooseJob.setText(QCoreApplication.translate("MainWindow", u"Choose job in GitLab\u2026", None))
        self.checkBox_advancedDebug.setText(QCoreApplication.translate("MainWindow", u"Advanced Debug", None))
        self.label_bmName.setText(QCoreApplication.translate("MainWindow", u"BM", None))
        self.label_bmSource.setText(QCoreApplication.translate("MainWindow", u"Not loaded", None))
        self.pushButton_loadBm.setText(QCoreApplication.translate("MainWindow", u"Load\u2026", None))
        self.label_fblName.setText(QCoreApplication.translate("MainWindow", u"FBL", None))
        self.label_fblSource.setText(QCoreApplication.translate("MainWindow", u"Not loaded", None))
        self.pushButton_loadFbl.setText(QCoreApplication.translate("MainWindow", u"Load\u2026", None))
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
        self.groupBox_firmware.setTitle(QCoreApplication.translate("MainWindow", u"Firmware", None))
        self.label_profile.setText(QCoreApplication.translate("MainWindow", u"Profile", None))
        self.pushButton_reloadProfiles.setText(QCoreApplication.translate("MainWindow", u"Reload", None))
        self.label_sourceRepo.setText(QCoreApplication.translate("MainWindow", u"Source repo", None))
        self.lineEdit_sourceRepo.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Folder of your source repo", None))
        self.pushButton_browseRepo.setText(QCoreApplication.translate("MainWindow", u"Browse", None))
#if QT_CONFIG(tooltip)
        self.pushButton_reloadRepo.setToolTip(QCoreApplication.translate("MainWindow", u"Read the source repo again: branch, commit and local changes", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_reloadRepo.setText(QCoreApplication.translate("MainWindow", u"Reload", None))
        self.label_repoSummary.setText(QCoreApplication.translate("MainWindow", u"Branch: - \u00b7 Commit: -", None))
        self.pushButton_checkout.setText(QCoreApplication.translate("MainWindow", u"Checkout\u2026", None))
        self.label_repoAutoHint.setText(QCoreApplication.translate("MainWindow", u"WFlash also reads the repo again each time you come back to its window.", None))
        self.groupBox_winidea.setTitle(QCoreApplication.translate("MainWindow", u"winIDEA", None))
        self.label_instance.setText(QCoreApplication.translate("MainWindow", u"Instance", None))
        self.pushButton_refreshInstances.setText(QCoreApplication.translate("MainWindow", u"Refresh", None))
        self.groupBox_afterFlash.setTitle(QCoreApplication.translate("MainWindow", u"After flash", None))
        self.checkBox_reset.setText(QCoreApplication.translate("MainWindow", u"Reset target", None))
        self.checkBox_run.setText(QCoreApplication.translate("MainWindow", u"Run after reset", None))
#if QT_CONFIG(tooltip)
        self.checkBox_verifyFlash.setToolTip(QCoreApplication.translate("MainWindow", u"Read samples of the flash back and compare them with the files. Adds about 3 minutes.", None))
#endif // QT_CONFIG(tooltip)
        self.checkBox_verifyFlash.setText(QCoreApplication.translate("MainWindow", u"Verify samples", None))
        self.label_verifyHint.setText(QCoreApplication.translate("MainWindow", u"Verify samples reads parts of the flash back and compares them with the files. Adds about 3 minutes.", None))
        self.pushButton_preferences.setText(QCoreApplication.translate("MainWindow", u"Preferences\u2026", None))
        self.tabWidget_main.setTabText(self.tabWidget_main.indexOf(self.tab_setting), QCoreApplication.translate("MainWindow", u"Setting", None))
        self.pushButton_copyLog.setText(QCoreApplication.translate("MainWindow", u"Copy", None))
        self.pushButton_clearLog.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.pushButton_exportBundle.setText(QCoreApplication.translate("MainWindow", u"Export debug bundle\u2026", None))
        self.tabWidget_output.setTabText(self.tabWidget_output.indexOf(self.tab_information), QCoreApplication.translate("MainWindow", u"Information", None))
    # retranslateUi


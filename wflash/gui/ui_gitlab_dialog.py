# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gitlab_dialog.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPlainTextEdit, QProgressBar, QPushButton,
    QSizePolicy, QSpacerItem, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_GitlabDialog(object):
    def setupUi(self, GitlabDialog):
        if not GitlabDialog.objectName():
            GitlabDialog.setObjectName(u"GitlabDialog")
        GitlabDialog.resize(880, 720)
        self.verticalLayout_gitlabDialog = QVBoxLayout(GitlabDialog)
        self.verticalLayout_gitlabDialog.setObjectName(u"verticalLayout_gitlabDialog")
        self.tabWidget_source = QTabWidget(GitlabDialog)
        self.tabWidget_source.setObjectName(u"tabWidget_source")
        self.tab_ciArtifact = QWidget()
        self.tab_ciArtifact.setObjectName(u"tab_ciArtifact")
        self.verticalLayout_ciArtifact = QVBoxLayout(self.tab_ciArtifact)
        self.verticalLayout_ciArtifact.setObjectName(u"verticalLayout_ciArtifact")
        self.gridLayout_ciArtifact = QGridLayout()
        self.gridLayout_ciArtifact.setObjectName(u"gridLayout_ciArtifact")
        self.label_ciProject = QLabel(self.tab_ciArtifact)
        self.label_ciProject.setObjectName(u"label_ciProject")

        self.gridLayout_ciArtifact.addWidget(self.label_ciProject, 0, 0, 1, 1)

        self.horizontalLayout_ciProject = QHBoxLayout()
        self.horizontalLayout_ciProject.setObjectName(u"horizontalLayout_ciProject")
        self.lineEdit_ciProject = QLineEdit(self.tab_ciArtifact)
        self.lineEdit_ciProject.setObjectName(u"lineEdit_ciProject")

        self.horizontalLayout_ciProject.addWidget(self.lineEdit_ciProject)

        self.label_ciProjectSource = QLabel(self.tab_ciArtifact)
        self.label_ciProjectSource.setObjectName(u"label_ciProjectSource")

        self.horizontalLayout_ciProject.addWidget(self.label_ciProjectSource)


        self.gridLayout_ciArtifact.addLayout(self.horizontalLayout_ciProject, 0, 1, 1, 1)

        self.label_ref = QLabel(self.tab_ciArtifact)
        self.label_ref.setObjectName(u"label_ref")

        self.gridLayout_ciArtifact.addWidget(self.label_ref, 1, 0, 1, 1)

        self.horizontalLayout_ref = QHBoxLayout()
        self.horizontalLayout_ref.setObjectName(u"horizontalLayout_ref")
        self.comboBox_ref = QComboBox(self.tab_ciArtifact)
        self.comboBox_ref.setObjectName(u"comboBox_ref")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.comboBox_ref.sizePolicy().hasHeightForWidth())
        self.comboBox_ref.setSizePolicy(sizePolicy)
        self.comboBox_ref.setEditable(True)
        self.comboBox_ref.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.horizontalLayout_ref.addWidget(self.comboBox_ref)

        self.pushButton_loadRefs = QPushButton(self.tab_ciArtifact)
        self.pushButton_loadRefs.setObjectName(u"pushButton_loadRefs")

        self.horizontalLayout_ref.addWidget(self.pushButton_loadRefs)


        self.gridLayout_ciArtifact.addLayout(self.horizontalLayout_ref, 1, 1, 1, 1)

        self.label_jobName = QLabel(self.tab_ciArtifact)
        self.label_jobName.setObjectName(u"label_jobName")

        self.gridLayout_ciArtifact.addWidget(self.label_jobName, 2, 0, 1, 1)

        self.comboBox_jobName = QComboBox(self.tab_ciArtifact)
        self.comboBox_jobName.setObjectName(u"comboBox_jobName")
        self.comboBox_jobName.setEditable(True)
        self.comboBox_jobName.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.gridLayout_ciArtifact.addWidget(self.comboBox_jobName, 2, 1, 1, 1)


        self.verticalLayout_ciArtifact.addLayout(self.gridLayout_ciArtifact)

        self.horizontalLayout_ciActions = QHBoxLayout()
        self.horizontalLayout_ciActions.setObjectName(u"horizontalLayout_ciActions")
        self.pushButton_downloadSelected = QPushButton(self.tab_ciArtifact)
        self.pushButton_downloadSelected.setObjectName(u"pushButton_downloadSelected")

        self.horizontalLayout_ciActions.addWidget(self.pushButton_downloadSelected)

        self.pushButton_browseJobs = QPushButton(self.tab_ciArtifact)
        self.pushButton_browseJobs.setObjectName(u"pushButton_browseJobs")

        self.horizontalLayout_ciActions.addWidget(self.pushButton_browseJobs)

        self.horizontalSpacer_ciActions = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_ciActions.addItem(self.horizontalSpacer_ciActions)


        self.verticalLayout_ciArtifact.addLayout(self.horizontalLayout_ciActions)

        self.tableWidget_jobs = QTableWidget(self.tab_ciArtifact)
        if (self.tableWidget_jobs.columnCount() < 6):
            self.tableWidget_jobs.setColumnCount(6)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget_jobs.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget_jobs.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget_jobs.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.tableWidget_jobs.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.tableWidget_jobs.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.tableWidget_jobs.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        self.tableWidget_jobs.setObjectName(u"tableWidget_jobs")
        self.tableWidget_jobs.setMinimumSize(QSize(0, 128))
        self.tableWidget_jobs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableWidget_jobs.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tableWidget_jobs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tableWidget_jobs.verticalHeader().setVisible(False)

        self.verticalLayout_ciArtifact.addWidget(self.tableWidget_jobs)

        self.tabWidget_source.addTab(self.tab_ciArtifact, "")

        self.verticalLayout_gitlabDialog.addWidget(self.tabWidget_source)

        self.horizontalLayout_download = QHBoxLayout()
        self.horizontalLayout_download.setObjectName(u"horizontalLayout_download")
        self.progressBar_download = QProgressBar(GitlabDialog)
        self.progressBar_download.setObjectName(u"progressBar_download")
        sizePolicy.setHeightForWidth(self.progressBar_download.sizePolicy().hasHeightForWidth())
        self.progressBar_download.setSizePolicy(sizePolicy)
        self.progressBar_download.setMaximumSize(QSize(16777215, 20))
        self.progressBar_download.setValue(0)
        self.progressBar_download.setTextVisible(False)

        self.horizontalLayout_download.addWidget(self.progressBar_download)

        self.label_downloadStatus = QLabel(GitlabDialog)
        self.label_downloadStatus.setObjectName(u"label_downloadStatus")
        self.label_downloadStatus.setMinimumSize(QSize(220, 0))

        self.horizontalLayout_download.addWidget(self.label_downloadStatus)

        self.pushButton_stopDownload = QPushButton(GitlabDialog)
        self.pushButton_stopDownload.setObjectName(u"pushButton_stopDownload")
        self.pushButton_stopDownload.setEnabled(False)

        self.horizontalLayout_download.addWidget(self.pushButton_stopDownload)


        self.verticalLayout_gitlabDialog.addLayout(self.horizontalLayout_download)

        self.label_gitlabLog = QLabel(GitlabDialog)
        self.label_gitlabLog.setObjectName(u"label_gitlabLog")

        self.verticalLayout_gitlabDialog.addWidget(self.label_gitlabLog)

        self.plainTextEdit_gitlabLog = QPlainTextEdit(GitlabDialog)
        self.plainTextEdit_gitlabLog.setObjectName(u"plainTextEdit_gitlabLog")
        self.plainTextEdit_gitlabLog.setMaximumSize(QSize(16777215, 120))
        self.plainTextEdit_gitlabLog.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.plainTextEdit_gitlabLog.setReadOnly(True)
        self.plainTextEdit_gitlabLog.setMaximumBlockCount(2000)

        self.verticalLayout_gitlabDialog.addWidget(self.plainTextEdit_gitlabLog)

        self.horizontalLayout_dialogButtons = QHBoxLayout()
        self.horizontalLayout_dialogButtons.setObjectName(u"horizontalLayout_dialogButtons")
        self.horizontalSpacer_dialogButtons = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_dialogButtons.addItem(self.horizontalSpacer_dialogButtons)

        self.pushButton_cancel = QPushButton(GitlabDialog)
        self.pushButton_cancel.setObjectName(u"pushButton_cancel")
        self.pushButton_cancel.setAutoDefault(False)

        self.horizontalLayout_dialogButtons.addWidget(self.pushButton_cancel)


        self.verticalLayout_gitlabDialog.addLayout(self.horizontalLayout_dialogButtons)

#if QT_CONFIG(shortcut)
        self.label_ciProject.setBuddy(self.lineEdit_ciProject)
        self.label_ref.setBuddy(self.comboBox_ref)
        self.label_jobName.setBuddy(self.comboBox_jobName)
        self.label_gitlabLog.setBuddy(self.plainTextEdit_gitlabLog)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.tabWidget_source, self.lineEdit_ciProject)
        QWidget.setTabOrder(self.lineEdit_ciProject, self.comboBox_ref)
        QWidget.setTabOrder(self.comboBox_ref, self.pushButton_loadRefs)
        QWidget.setTabOrder(self.pushButton_loadRefs, self.comboBox_jobName)
        QWidget.setTabOrder(self.comboBox_jobName, self.pushButton_downloadSelected)
        QWidget.setTabOrder(self.pushButton_downloadSelected, self.pushButton_browseJobs)
        QWidget.setTabOrder(self.pushButton_browseJobs, self.tableWidget_jobs)
        QWidget.setTabOrder(self.tableWidget_jobs, self.pushButton_stopDownload)
        QWidget.setTabOrder(self.pushButton_stopDownload, self.pushButton_cancel)

        self.retranslateUi(GitlabDialog)

        self.tabWidget_source.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(GitlabDialog)
    # setupUi

    def retranslateUi(self, GitlabDialog):
        GitlabDialog.setWindowTitle(QCoreApplication.translate("GitlabDialog", u"Load from GitLab", None))
        self.label_ciProject.setText(QCoreApplication.translate("GitlabDialog", u"Project:", None))
        self.lineEdit_ciProject.setPlaceholderText(QCoreApplication.translate("GitlabDialog", u"group/project (empty = the profile's project)", None))
        self.label_ciProjectSource.setText(QCoreApplication.translate("GitlabDialog", u"from profile", None))
        self.label_ref.setText(QCoreApplication.translate("GitlabDialog", u"Branch/tag:", None))
        self.pushButton_loadRefs.setText(QCoreApplication.translate("GitlabDialog", u"Load branches/tags", None))
        self.label_jobName.setText(QCoreApplication.translate("GitlabDialog", u"Job name:", None))
        self.pushButton_downloadSelected.setText(QCoreApplication.translate("GitlabDialog", u"Download Selected Artifact", None))
        self.pushButton_browseJobs.setText(QCoreApplication.translate("GitlabDialog", u"Browse jobs\u2026", None))
        ___qtablewidgetitem = self.tableWidget_jobs.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("GitlabDialog", u"Pipeline", None))
        ___qtablewidgetitem1 = self.tableWidget_jobs.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("GitlabDialog", u"Job", None))
        ___qtablewidgetitem2 = self.tableWidget_jobs.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("GitlabDialog", u"Ref", None))
        ___qtablewidgetitem3 = self.tableWidget_jobs.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("GitlabDialog", u"Status", None))
        ___qtablewidgetitem4 = self.tableWidget_jobs.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("GitlabDialog", u"When", None))
        ___qtablewidgetitem5 = self.tableWidget_jobs.horizontalHeaderItem(5)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("GitlabDialog", u"Download", None))
        self.tabWidget_source.setTabText(self.tabWidget_source.indexOf(self.tab_ciArtifact), QCoreApplication.translate("GitlabDialog", u"CI Artifact", None))
        self.label_downloadStatus.setText(QCoreApplication.translate("GitlabDialog", u"Ready", None))
        self.pushButton_stopDownload.setText(QCoreApplication.translate("GitlabDialog", u"Stop", None))
        self.label_gitlabLog.setText(QCoreApplication.translate("GitlabDialog", u"GitLab log", None))
        self.pushButton_cancel.setText(QCoreApplication.translate("GitlabDialog", u"Cancel", None))
    # retranslateUi


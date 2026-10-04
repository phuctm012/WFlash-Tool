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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QDialog, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPlainTextEdit,
    QProgressBar, QPushButton, QSizePolicy, QSpacerItem,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget)

class Ui_GitlabDialog(object):
    def setupUi(self, GitlabDialog):
        if not GitlabDialog.objectName():
            GitlabDialog.setObjectName(u"GitlabDialog")
        GitlabDialog.resize(880, 720)
        GitlabDialog.setMinimumSize(QSize(760, 600))
        self.verticalLayout_gitlabDialog = QVBoxLayout(GitlabDialog)
        self.verticalLayout_gitlabDialog.setObjectName(u"verticalLayout_gitlabDialog")
        self.groupBox_connection = QGroupBox(GitlabDialog)
        self.groupBox_connection.setObjectName(u"groupBox_connection")
        self.gridLayout_connection = QGridLayout(self.groupBox_connection)
        self.gridLayout_connection.setObjectName(u"gridLayout_connection")
        self.label_gitlabUrl = QLabel(self.groupBox_connection)
        self.label_gitlabUrl.setObjectName(u"label_gitlabUrl")

        self.gridLayout_connection.addWidget(self.label_gitlabUrl, 0, 0, 1, 1)

        self.lineEdit_gitlabUrl = QLineEdit(self.groupBox_connection)
        self.lineEdit_gitlabUrl.setObjectName(u"lineEdit_gitlabUrl")

        self.gridLayout_connection.addWidget(self.lineEdit_gitlabUrl, 0, 1, 1, 1)

        self.label_token = QLabel(self.groupBox_connection)
        self.label_token.setObjectName(u"label_token")

        self.gridLayout_connection.addWidget(self.label_token, 1, 0, 1, 1)

        self.lineEdit_token = QLineEdit(self.groupBox_connection)
        self.lineEdit_token.setObjectName(u"lineEdit_token")
        self.lineEdit_token.setEchoMode(QLineEdit.EchoMode.Password)

        self.gridLayout_connection.addWidget(self.lineEdit_token, 1, 1, 1, 1)

        self.checkBox_verifyTls = QCheckBox(self.groupBox_connection)
        self.checkBox_verifyTls.setObjectName(u"checkBox_verifyTls")
        self.checkBox_verifyTls.setChecked(True)

        self.gridLayout_connection.addWidget(self.checkBox_verifyTls, 2, 1, 1, 1)

        self.label_caBundle = QLabel(self.groupBox_connection)
        self.label_caBundle.setObjectName(u"label_caBundle")

        self.gridLayout_connection.addWidget(self.label_caBundle, 3, 0, 1, 1)

        self.horizontalLayout_caBundle = QHBoxLayout()
        self.horizontalLayout_caBundle.setObjectName(u"horizontalLayout_caBundle")
        self.lineEdit_caBundle = QLineEdit(self.groupBox_connection)
        self.lineEdit_caBundle.setObjectName(u"lineEdit_caBundle")

        self.horizontalLayout_caBundle.addWidget(self.lineEdit_caBundle)

        self.pushButton_browseCa = QPushButton(self.groupBox_connection)
        self.pushButton_browseCa.setObjectName(u"pushButton_browseCa")

        self.horizontalLayout_caBundle.addWidget(self.pushButton_browseCa)


        self.gridLayout_connection.addLayout(self.horizontalLayout_caBundle, 3, 1, 1, 1)

        self.label_connectionHint = QLabel(self.groupBox_connection)
        self.label_connectionHint.setObjectName(u"label_connectionHint")
        self.label_connectionHint.setWordWrap(True)

        self.gridLayout_connection.addWidget(self.label_connectionHint, 4, 0, 1, 2)


        self.verticalLayout_gitlabDialog.addWidget(self.groupBox_connection)

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
        self.tab_packageRegistry = QWidget()
        self.tab_packageRegistry.setObjectName(u"tab_packageRegistry")
        self.verticalLayout_packageRegistry = QVBoxLayout(self.tab_packageRegistry)
        self.verticalLayout_packageRegistry.setObjectName(u"verticalLayout_packageRegistry")
        self.gridLayout_package = QGridLayout()
        self.gridLayout_package.setObjectName(u"gridLayout_package")
        self.label_pkgProject = QLabel(self.tab_packageRegistry)
        self.label_pkgProject.setObjectName(u"label_pkgProject")

        self.gridLayout_package.addWidget(self.label_pkgProject, 0, 0, 1, 1)

        self.lineEdit_pkgProject = QLineEdit(self.tab_packageRegistry)
        self.lineEdit_pkgProject.setObjectName(u"lineEdit_pkgProject")

        self.gridLayout_package.addWidget(self.lineEdit_pkgProject, 0, 1, 1, 1)

        self.label_packageName = QLabel(self.tab_packageRegistry)
        self.label_packageName.setObjectName(u"label_packageName")

        self.gridLayout_package.addWidget(self.label_packageName, 1, 0, 1, 1)

        self.lineEdit_packageName = QLineEdit(self.tab_packageRegistry)
        self.lineEdit_packageName.setObjectName(u"lineEdit_packageName")

        self.gridLayout_package.addWidget(self.lineEdit_packageName, 1, 1, 1, 1)


        self.verticalLayout_packageRegistry.addLayout(self.gridLayout_package)

        self.horizontalLayout_packageActions = QHBoxLayout()
        self.horizontalLayout_packageActions.setObjectName(u"horizontalLayout_packageActions")
        self.pushButton_fetchLatest = QPushButton(self.tab_packageRegistry)
        self.pushButton_fetchLatest.setObjectName(u"pushButton_fetchLatest")

        self.horizontalLayout_packageActions.addWidget(self.pushButton_fetchLatest)

        self.pushButton_browseVersions = QPushButton(self.tab_packageRegistry)
        self.pushButton_browseVersions.setObjectName(u"pushButton_browseVersions")

        self.horizontalLayout_packageActions.addWidget(self.pushButton_browseVersions)

        self.horizontalSpacer_packageActions = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_packageActions.addItem(self.horizontalSpacer_packageActions)


        self.verticalLayout_packageRegistry.addLayout(self.horizontalLayout_packageActions)

        self.tableWidget_versions = QTableWidget(self.tab_packageRegistry)
        if (self.tableWidget_versions.columnCount() < 3):
            self.tableWidget_versions.setColumnCount(3)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.tableWidget_versions.setHorizontalHeaderItem(0, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.tableWidget_versions.setHorizontalHeaderItem(1, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.tableWidget_versions.setHorizontalHeaderItem(2, __qtablewidgetitem8)
        self.tableWidget_versions.setObjectName(u"tableWidget_versions")
        self.tableWidget_versions.setMinimumSize(QSize(0, 128))
        self.tableWidget_versions.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableWidget_versions.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tableWidget_versions.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tableWidget_versions.verticalHeader().setVisible(False)

        self.verticalLayout_packageRegistry.addWidget(self.tableWidget_versions)

        self.tabWidget_source.addTab(self.tab_packageRegistry, "")

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
        self.label_gitlabUrl.setBuddy(self.lineEdit_gitlabUrl)
        self.label_token.setBuddy(self.lineEdit_token)
        self.label_caBundle.setBuddy(self.lineEdit_caBundle)
        self.label_ciProject.setBuddy(self.lineEdit_ciProject)
        self.label_ref.setBuddy(self.comboBox_ref)
        self.label_jobName.setBuddy(self.comboBox_jobName)
        self.label_pkgProject.setBuddy(self.lineEdit_pkgProject)
        self.label_packageName.setBuddy(self.lineEdit_packageName)
        self.label_gitlabLog.setBuddy(self.plainTextEdit_gitlabLog)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.lineEdit_gitlabUrl, self.lineEdit_token)
        QWidget.setTabOrder(self.lineEdit_token, self.checkBox_verifyTls)
        QWidget.setTabOrder(self.checkBox_verifyTls, self.lineEdit_caBundle)
        QWidget.setTabOrder(self.lineEdit_caBundle, self.pushButton_browseCa)
        QWidget.setTabOrder(self.pushButton_browseCa, self.tabWidget_source)
        QWidget.setTabOrder(self.tabWidget_source, self.lineEdit_ciProject)
        QWidget.setTabOrder(self.lineEdit_ciProject, self.comboBox_ref)
        QWidget.setTabOrder(self.comboBox_ref, self.pushButton_loadRefs)
        QWidget.setTabOrder(self.pushButton_loadRefs, self.comboBox_jobName)
        QWidget.setTabOrder(self.comboBox_jobName, self.pushButton_downloadSelected)
        QWidget.setTabOrder(self.pushButton_downloadSelected, self.pushButton_browseJobs)
        QWidget.setTabOrder(self.pushButton_browseJobs, self.tableWidget_jobs)
        QWidget.setTabOrder(self.tableWidget_jobs, self.lineEdit_pkgProject)
        QWidget.setTabOrder(self.lineEdit_pkgProject, self.lineEdit_packageName)
        QWidget.setTabOrder(self.lineEdit_packageName, self.pushButton_fetchLatest)
        QWidget.setTabOrder(self.pushButton_fetchLatest, self.pushButton_browseVersions)
        QWidget.setTabOrder(self.pushButton_browseVersions, self.tableWidget_versions)
        QWidget.setTabOrder(self.tableWidget_versions, self.pushButton_stopDownload)
        QWidget.setTabOrder(self.pushButton_stopDownload, self.pushButton_cancel)

        self.retranslateUi(GitlabDialog)

        self.tabWidget_source.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(GitlabDialog)
    # setupUi

    def retranslateUi(self, GitlabDialog):
        GitlabDialog.setWindowTitle(QCoreApplication.translate("GitlabDialog", u"Load from GitLab", None))
        self.groupBox_connection.setTitle(QCoreApplication.translate("GitlabDialog", u"GitLab Connection", None))
        self.label_gitlabUrl.setText(QCoreApplication.translate("GitlabDialog", u"Instance URL:", None))
        self.lineEdit_gitlabUrl.setPlaceholderText(QCoreApplication.translate("GitlabDialog", u"https://gitlab.company.com", None))
        self.label_token.setText(QCoreApplication.translate("GitlabDialog", u"Access token:", None))
        self.lineEdit_token.setPlaceholderText(QCoreApplication.translate("GitlabDialog", u"Personal Access Token (scope read_api)", None))
        self.checkBox_verifyTls.setText(QCoreApplication.translate("GitlabDialog", u"Verify TLS certificate (recommended)", None))
        self.label_caBundle.setText(QCoreApplication.translate("GitlabDialog", u"CA bundle:", None))
        self.lineEdit_caBundle.setPlaceholderText(QCoreApplication.translate("GitlabDialog", u"Optional: .pem file for an internal certificate", None))
        self.pushButton_browseCa.setText(QCoreApplication.translate("GitlabDialog", u"Browse\u2026", None))
        self.label_connectionHint.setText(QCoreApplication.translate("GitlabDialog", u"Required token scope: read_api (branches/tags, pipelines, jobs, artifacts, packages). The token is stored in the system keyring (Windows Credential Manager), never in a file.", None))
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
        self.label_pkgProject.setText(QCoreApplication.translate("GitlabDialog", u"Project:", None))
        self.lineEdit_pkgProject.setPlaceholderText(QCoreApplication.translate("GitlabDialog", u"group/project holding the generic package", None))
        self.label_packageName.setText(QCoreApplication.translate("GitlabDialog", u"Package name:", None))
        self.lineEdit_packageName.setPlaceholderText(QCoreApplication.translate("GitlabDialog", u"e.g. saf85xx-firmware", None))
        self.pushButton_fetchLatest.setText(QCoreApplication.translate("GitlabDialog", u"Fetch Latest Version", None))
        self.pushButton_browseVersions.setText(QCoreApplication.translate("GitlabDialog", u"Browse versions\u2026", None))
        ___qtablewidgetitem6 = self.tableWidget_versions.horizontalHeaderItem(0)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("GitlabDialog", u"Version", None))
        ___qtablewidgetitem7 = self.tableWidget_versions.horizontalHeaderItem(1)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("GitlabDialog", u"Uploaded", None))
        ___qtablewidgetitem8 = self.tableWidget_versions.horizontalHeaderItem(2)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("GitlabDialog", u"Download", None))
        self.tabWidget_source.setTabText(self.tabWidget_source.indexOf(self.tab_packageRegistry), QCoreApplication.translate("GitlabDialog", u"Package Registry", None))
        self.label_downloadStatus.setText(QCoreApplication.translate("GitlabDialog", u"Ready", None))
        self.pushButton_stopDownload.setText(QCoreApplication.translate("GitlabDialog", u"Stop", None))
        self.label_gitlabLog.setText(QCoreApplication.translate("GitlabDialog", u"GitLab log", None))
        self.pushButton_cancel.setText(QCoreApplication.translate("GitlabDialog", u"Cancel", None))
    # retranslateUi


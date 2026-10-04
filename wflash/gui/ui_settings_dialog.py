# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'settings_dialog.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QDialog,
    QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpinBox,
    QVBoxLayout, QWidget)

class Ui_SettingsDialog(object):
    def setupUi(self, SettingsDialog):
        if not SettingsDialog.objectName():
            SettingsDialog.setObjectName(u"SettingsDialog")
        SettingsDialog.resize(600, 320)
        SettingsDialog.setMinimumSize(QSize(560, 0))
        self.verticalLayout_settings = QVBoxLayout(SettingsDialog)
        self.verticalLayout_settings.setObjectName(u"verticalLayout_settings")
        self.formLayout_settings = QFormLayout()
        self.formLayout_settings.setObjectName(u"formLayout_settings")
        self.label_gitlabUrl = QLabel(SettingsDialog)
        self.label_gitlabUrl.setObjectName(u"label_gitlabUrl")

        self.formLayout_settings.setWidget(0, QFormLayout.ItemRole.LabelRole, self.label_gitlabUrl)

        self.lineEdit_gitlabUrl = QLineEdit(SettingsDialog)
        self.lineEdit_gitlabUrl.setObjectName(u"lineEdit_gitlabUrl")

        self.formLayout_settings.setWidget(0, QFormLayout.ItemRole.FieldRole, self.lineEdit_gitlabUrl)

        self.label_token = QLabel(SettingsDialog)
        self.label_token.setObjectName(u"label_token")

        self.formLayout_settings.setWidget(1, QFormLayout.ItemRole.LabelRole, self.label_token)

        self.lineEdit_token = QLineEdit(SettingsDialog)
        self.lineEdit_token.setObjectName(u"lineEdit_token")
        self.lineEdit_token.setEchoMode(QLineEdit.EchoMode.Password)

        self.formLayout_settings.setWidget(1, QFormLayout.ItemRole.FieldRole, self.lineEdit_token)

        self.label_caBundle = QLabel(SettingsDialog)
        self.label_caBundle.setObjectName(u"label_caBundle")

        self.formLayout_settings.setWidget(2, QFormLayout.ItemRole.LabelRole, self.label_caBundle)

        self.horizontalLayout_caBundle = QHBoxLayout()
        self.horizontalLayout_caBundle.setObjectName(u"horizontalLayout_caBundle")
        self.lineEdit_caBundle = QLineEdit(SettingsDialog)
        self.lineEdit_caBundle.setObjectName(u"lineEdit_caBundle")

        self.horizontalLayout_caBundle.addWidget(self.lineEdit_caBundle)

        self.pushButton_browseCaBundle = QPushButton(SettingsDialog)
        self.pushButton_browseCaBundle.setObjectName(u"pushButton_browseCaBundle")

        self.horizontalLayout_caBundle.addWidget(self.pushButton_browseCaBundle)


        self.formLayout_settings.setLayout(2, QFormLayout.ItemRole.FieldRole, self.horizontalLayout_caBundle)

        self.label_cacheDir = QLabel(SettingsDialog)
        self.label_cacheDir.setObjectName(u"label_cacheDir")

        self.formLayout_settings.setWidget(3, QFormLayout.ItemRole.LabelRole, self.label_cacheDir)

        self.horizontalLayout_cacheDir = QHBoxLayout()
        self.horizontalLayout_cacheDir.setObjectName(u"horizontalLayout_cacheDir")
        self.lineEdit_cacheDir = QLineEdit(SettingsDialog)
        self.lineEdit_cacheDir.setObjectName(u"lineEdit_cacheDir")

        self.horizontalLayout_cacheDir.addWidget(self.lineEdit_cacheDir)

        self.pushButton_browseCacheDir = QPushButton(SettingsDialog)
        self.pushButton_browseCacheDir.setObjectName(u"pushButton_browseCacheDir")

        self.horizontalLayout_cacheDir.addWidget(self.pushButton_browseCacheDir)

        self.pushButton_clearCache = QPushButton(SettingsDialog)
        self.pushButton_clearCache.setObjectName(u"pushButton_clearCache")

        self.horizontalLayout_cacheDir.addWidget(self.pushButton_clearCache)


        self.formLayout_settings.setLayout(3, QFormLayout.ItemRole.FieldRole, self.horizontalLayout_cacheDir)

        self.label_maxCachedJobs = QLabel(SettingsDialog)
        self.label_maxCachedJobs.setObjectName(u"label_maxCachedJobs")

        self.formLayout_settings.setWidget(4, QFormLayout.ItemRole.LabelRole, self.label_maxCachedJobs)

        self.spinBox_maxCachedJobs = QSpinBox(SettingsDialog)
        self.spinBox_maxCachedJobs.setObjectName(u"spinBox_maxCachedJobs")
        self.spinBox_maxCachedJobs.setMinimum(1)
        self.spinBox_maxCachedJobs.setMaximum(100)
        self.spinBox_maxCachedJobs.setValue(10)

        self.formLayout_settings.setWidget(4, QFormLayout.ItemRole.FieldRole, self.spinBox_maxCachedJobs)

        self.label_profilesDir = QLabel(SettingsDialog)
        self.label_profilesDir.setObjectName(u"label_profilesDir")

        self.formLayout_settings.setWidget(5, QFormLayout.ItemRole.LabelRole, self.label_profilesDir)

        self.horizontalLayout_profilesDir = QHBoxLayout()
        self.horizontalLayout_profilesDir.setObjectName(u"horizontalLayout_profilesDir")
        self.lineEdit_profilesDir = QLineEdit(SettingsDialog)
        self.lineEdit_profilesDir.setObjectName(u"lineEdit_profilesDir")

        self.horizontalLayout_profilesDir.addWidget(self.lineEdit_profilesDir)

        self.pushButton_browseProfilesDir = QPushButton(SettingsDialog)
        self.pushButton_browseProfilesDir.setObjectName(u"pushButton_browseProfilesDir")

        self.horizontalLayout_profilesDir.addWidget(self.pushButton_browseProfilesDir)


        self.formLayout_settings.setLayout(5, QFormLayout.ItemRole.FieldRole, self.horizontalLayout_profilesDir)

        self.checkBox_verbose = QCheckBox(SettingsDialog)
        self.checkBox_verbose.setObjectName(u"checkBox_verbose")

        self.formLayout_settings.setWidget(6, QFormLayout.ItemRole.FieldRole, self.checkBox_verbose)


        self.verticalLayout_settings.addLayout(self.formLayout_settings)

        self.label_error = QLabel(SettingsDialog)
        self.label_error.setObjectName(u"label_error")
        self.label_error.setStyleSheet(u"color: #d32f2f;")
        self.label_error.setWordWrap(True)

        self.verticalLayout_settings.addWidget(self.label_error)

        self.buttonBox_settings = QDialogButtonBox(SettingsDialog)
        self.buttonBox_settings.setObjectName(u"buttonBox_settings")
        self.buttonBox_settings.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout_settings.addWidget(self.buttonBox_settings)

#if QT_CONFIG(shortcut)
        self.label_gitlabUrl.setBuddy(self.lineEdit_gitlabUrl)
        self.label_token.setBuddy(self.lineEdit_token)
        self.label_caBundle.setBuddy(self.lineEdit_caBundle)
        self.label_cacheDir.setBuddy(self.lineEdit_cacheDir)
        self.label_maxCachedJobs.setBuddy(self.spinBox_maxCachedJobs)
        self.label_profilesDir.setBuddy(self.lineEdit_profilesDir)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(SettingsDialog)

        QMetaObject.connectSlotsByName(SettingsDialog)
    # setupUi

    def retranslateUi(self, SettingsDialog):
        SettingsDialog.setWindowTitle(QCoreApplication.translate("SettingsDialog", u"Settings", None))
        self.label_gitlabUrl.setText(QCoreApplication.translate("SettingsDialog", u"GitLab URL:", None))
        self.lineEdit_gitlabUrl.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"https://gitlab.company.com", None))
        self.label_token.setText(QCoreApplication.translate("SettingsDialog", u"Access token:", None))
        self.lineEdit_token.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"Personal Access Token (scope read_api)", None))
        self.label_caBundle.setText(QCoreApplication.translate("SettingsDialog", u"CA bundle:", None))
        self.lineEdit_caBundle.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"Optional: .pem file for an internal certificate", None))
        self.pushButton_browseCaBundle.setText(QCoreApplication.translate("SettingsDialog", u"Browse\u2026", None))
        self.label_cacheDir.setText(QCoreApplication.translate("SettingsDialog", u"Cache folder:", None))
        self.pushButton_browseCacheDir.setText(QCoreApplication.translate("SettingsDialog", u"Browse\u2026", None))
        self.pushButton_clearCache.setText(QCoreApplication.translate("SettingsDialog", u"Clear cache", None))
        self.label_maxCachedJobs.setText(QCoreApplication.translate("SettingsDialog", u"Cached jobs to keep:", None))
        self.label_profilesDir.setText(QCoreApplication.translate("SettingsDialog", u"Profiles folder:", None))
        self.pushButton_browseProfilesDir.setText(QCoreApplication.translate("SettingsDialog", u"Browse\u2026", None))
        self.checkBox_verbose.setText(QCoreApplication.translate("SettingsDialog", u"Verbose winIDEA call logging", None))
        self.label_error.setText("")
    # retranslateUi


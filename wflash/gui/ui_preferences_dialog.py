# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'preferences_dialog.ui'
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
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QSpinBox, QVBoxLayout, QWidget)

class Ui_PreferencesDialog(object):
    def setupUi(self, PreferencesDialog):
        if not PreferencesDialog.objectName():
            PreferencesDialog.setObjectName(u"PreferencesDialog")
        PreferencesDialog.resize(600, 260)
        PreferencesDialog.setMinimumSize(QSize(560, 0))
        self.verticalLayout_preferences = QVBoxLayout(PreferencesDialog)
        self.verticalLayout_preferences.setObjectName(u"verticalLayout_preferences")
        self.formLayout_preferences = QFormLayout()
        self.formLayout_preferences.setObjectName(u"formLayout_preferences")
        self.label_cacheDir = QLabel(PreferencesDialog)
        self.label_cacheDir.setObjectName(u"label_cacheDir")

        self.formLayout_preferences.setWidget(0, QFormLayout.ItemRole.LabelRole, self.label_cacheDir)

        self.horizontalLayout_cacheDir = QHBoxLayout()
        self.horizontalLayout_cacheDir.setObjectName(u"horizontalLayout_cacheDir")
        self.lineEdit_cacheDir = QLineEdit(PreferencesDialog)
        self.lineEdit_cacheDir.setObjectName(u"lineEdit_cacheDir")

        self.horizontalLayout_cacheDir.addWidget(self.lineEdit_cacheDir)

        self.pushButton_browseCacheDir = QPushButton(PreferencesDialog)
        self.pushButton_browseCacheDir.setObjectName(u"pushButton_browseCacheDir")

        self.horizontalLayout_cacheDir.addWidget(self.pushButton_browseCacheDir)

        self.pushButton_clearCache = QPushButton(PreferencesDialog)
        self.pushButton_clearCache.setObjectName(u"pushButton_clearCache")

        self.horizontalLayout_cacheDir.addWidget(self.pushButton_clearCache)


        self.formLayout_preferences.setLayout(0, QFormLayout.ItemRole.FieldRole, self.horizontalLayout_cacheDir)

        self.label_maxCachedJobs = QLabel(PreferencesDialog)
        self.label_maxCachedJobs.setObjectName(u"label_maxCachedJobs")

        self.formLayout_preferences.setWidget(1, QFormLayout.ItemRole.LabelRole, self.label_maxCachedJobs)

        self.spinBox_maxCachedJobs = QSpinBox(PreferencesDialog)
        self.spinBox_maxCachedJobs.setObjectName(u"spinBox_maxCachedJobs")
        self.spinBox_maxCachedJobs.setMinimum(1)
        self.spinBox_maxCachedJobs.setMaximum(100)
        self.spinBox_maxCachedJobs.setValue(10)

        self.formLayout_preferences.setWidget(1, QFormLayout.ItemRole.FieldRole, self.spinBox_maxCachedJobs)

        self.label_profilesDir = QLabel(PreferencesDialog)
        self.label_profilesDir.setObjectName(u"label_profilesDir")

        self.formLayout_preferences.setWidget(2, QFormLayout.ItemRole.LabelRole, self.label_profilesDir)

        self.horizontalLayout_profilesDir = QHBoxLayout()
        self.horizontalLayout_profilesDir.setObjectName(u"horizontalLayout_profilesDir")
        self.lineEdit_profilesDir = QLineEdit(PreferencesDialog)
        self.lineEdit_profilesDir.setObjectName(u"lineEdit_profilesDir")

        self.horizontalLayout_profilesDir.addWidget(self.lineEdit_profilesDir)

        self.pushButton_browseProfilesDir = QPushButton(PreferencesDialog)
        self.pushButton_browseProfilesDir.setObjectName(u"pushButton_browseProfilesDir")

        self.horizontalLayout_profilesDir.addWidget(self.pushButton_browseProfilesDir)


        self.formLayout_preferences.setLayout(2, QFormLayout.ItemRole.FieldRole, self.horizontalLayout_profilesDir)

        self.checkBox_verbose = QCheckBox(PreferencesDialog)
        self.checkBox_verbose.setObjectName(u"checkBox_verbose")

        self.formLayout_preferences.setWidget(3, QFormLayout.ItemRole.FieldRole, self.checkBox_verbose)

        self.checkBox_darkMode = QCheckBox(PreferencesDialog)
        self.checkBox_darkMode.setObjectName(u"checkBox_darkMode")

        self.formLayout_preferences.setWidget(4, QFormLayout.ItemRole.FieldRole, self.checkBox_darkMode)


        self.verticalLayout_preferences.addLayout(self.formLayout_preferences)

        self.label_error = QLabel(PreferencesDialog)
        self.label_error.setObjectName(u"label_error")
        self.label_error.setWordWrap(True)

        self.verticalLayout_preferences.addWidget(self.label_error)

        self.verticalSpacer_preferences = QSpacerItem(20, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_preferences.addItem(self.verticalSpacer_preferences)

        self.buttonBox_preferences = QDialogButtonBox(PreferencesDialog)
        self.buttonBox_preferences.setObjectName(u"buttonBox_preferences")
        self.buttonBox_preferences.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout_preferences.addWidget(self.buttonBox_preferences)

#if QT_CONFIG(shortcut)
        self.label_cacheDir.setBuddy(self.lineEdit_cacheDir)
        self.label_maxCachedJobs.setBuddy(self.spinBox_maxCachedJobs)
        self.label_profilesDir.setBuddy(self.lineEdit_profilesDir)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(PreferencesDialog)

        QMetaObject.connectSlotsByName(PreferencesDialog)
    # setupUi

    def retranslateUi(self, PreferencesDialog):
        PreferencesDialog.setWindowTitle(QCoreApplication.translate("PreferencesDialog", u"Preferences", None))
        self.label_cacheDir.setText(QCoreApplication.translate("PreferencesDialog", u"Cache folder:", None))
        self.pushButton_browseCacheDir.setText(QCoreApplication.translate("PreferencesDialog", u"Browse\u2026", None))
        self.pushButton_clearCache.setText(QCoreApplication.translate("PreferencesDialog", u"Clear cache", None))
        self.label_maxCachedJobs.setText(QCoreApplication.translate("PreferencesDialog", u"Cached downloads to keep:", None))
        self.label_profilesDir.setText(QCoreApplication.translate("PreferencesDialog", u"Profiles folder:", None))
        self.pushButton_browseProfilesDir.setText(QCoreApplication.translate("PreferencesDialog", u"Browse\u2026", None))
        self.checkBox_verbose.setText(QCoreApplication.translate("PreferencesDialog", u"Verbose winIDEA call logging", None))
        self.checkBox_darkMode.setText(QCoreApplication.translate("PreferencesDialog", u"Dark mode", None))
        self.label_error.setText("")
    # retranslateUi


# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'checkout_dialog.ui'
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
    QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

class Ui_CheckoutDialog(object):
    def setupUi(self, CheckoutDialog):
        if not CheckoutDialog.objectName():
            CheckoutDialog.setObjectName(u"CheckoutDialog")
        CheckoutDialog.resize(760, 480)
        self.verticalLayout_checkout = QVBoxLayout(CheckoutDialog)
        self.verticalLayout_checkout.setObjectName(u"verticalLayout_checkout")
        self.label_currentState = QLabel(CheckoutDialog)
        self.label_currentState.setObjectName(u"label_currentState")

        self.verticalLayout_checkout.addWidget(self.label_currentState)

        self.horizontalLayout_branch = QHBoxLayout()
        self.horizontalLayout_branch.setObjectName(u"horizontalLayout_branch")
        self.label_branch = QLabel(CheckoutDialog)
        self.label_branch.setObjectName(u"label_branch")

        self.horizontalLayout_branch.addWidget(self.label_branch)

        self.comboBox_branch = QComboBox(CheckoutDialog)
        self.comboBox_branch.setObjectName(u"comboBox_branch")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.comboBox_branch.sizePolicy().hasHeightForWidth())
        self.comboBox_branch.setSizePolicy(sizePolicy)

        self.horizontalLayout_branch.addWidget(self.comboBox_branch)

        self.pushButton_fetch = QPushButton(CheckoutDialog)
        self.pushButton_fetch.setObjectName(u"pushButton_fetch")

        self.horizontalLayout_branch.addWidget(self.pushButton_fetch)


        self.verticalLayout_checkout.addLayout(self.horizontalLayout_branch)

        self.label_commits = QLabel(CheckoutDialog)
        self.label_commits.setObjectName(u"label_commits")

        self.verticalLayout_checkout.addWidget(self.label_commits)

        self.tableWidget_commits = QTableWidget(CheckoutDialog)
        if (self.tableWidget_commits.columnCount() < 4):
            self.tableWidget_commits.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget_commits.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget_commits.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget_commits.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.tableWidget_commits.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.tableWidget_commits.setObjectName(u"tableWidget_commits")
        self.tableWidget_commits.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableWidget_commits.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tableWidget_commits.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tableWidget_commits.setWordWrap(False)
        self.tableWidget_commits.verticalHeader().setVisible(False)

        self.verticalLayout_checkout.addWidget(self.tableWidget_commits)

        self.label_checkoutError = QLabel(CheckoutDialog)
        self.label_checkoutError.setObjectName(u"label_checkoutError")
        self.label_checkoutError.setWordWrap(True)

        self.verticalLayout_checkout.addWidget(self.label_checkoutError)

        self.label_checkoutNote = QLabel(CheckoutDialog)
        self.label_checkoutNote.setObjectName(u"label_checkoutNote")
        self.label_checkoutNote.setWordWrap(True)

        self.verticalLayout_checkout.addWidget(self.label_checkoutNote)

        self.horizontalLayout_checkoutButtons = QHBoxLayout()
        self.horizontalLayout_checkoutButtons.setObjectName(u"horizontalLayout_checkoutButtons")
        self.label_checkoutStatus = QLabel(CheckoutDialog)
        self.label_checkoutStatus.setObjectName(u"label_checkoutStatus")

        self.horizontalLayout_checkoutButtons.addWidget(self.label_checkoutStatus)

        self.horizontalSpacer_checkoutButtons = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_checkoutButtons.addItem(self.horizontalSpacer_checkoutButtons)

        self.pushButton_cancelCheckout = QPushButton(CheckoutDialog)
        self.pushButton_cancelCheckout.setObjectName(u"pushButton_cancelCheckout")

        self.horizontalLayout_checkoutButtons.addWidget(self.pushButton_cancelCheckout)

        self.pushButton_checkout = QPushButton(CheckoutDialog)
        self.pushButton_checkout.setObjectName(u"pushButton_checkout")

        self.horizontalLayout_checkoutButtons.addWidget(self.pushButton_checkout)


        self.verticalLayout_checkout.addLayout(self.horizontalLayout_checkoutButtons)


        self.retranslateUi(CheckoutDialog)

        self.pushButton_checkout.setDefault(True)


        QMetaObject.connectSlotsByName(CheckoutDialog)
    # setupUi

    def retranslateUi(self, CheckoutDialog):
        CheckoutDialog.setWindowTitle(QCoreApplication.translate("CheckoutDialog", u"Checkout source repo", None))
        self.label_currentState.setText(QCoreApplication.translate("CheckoutDialog", u"Current: -", None))
        self.label_branch.setText(QCoreApplication.translate("CheckoutDialog", u"Branch", None))
#if QT_CONFIG(tooltip)
        self.comboBox_branch.setToolTip(QCoreApplication.translate("CheckoutDialog", u"Local branches and branches on the remote", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_fetch.setText(QCoreApplication.translate("CheckoutDialog", u"Fetch", None))
#if QT_CONFIG(tooltip)
        self.pushButton_fetch.setToolTip(QCoreApplication.translate("CheckoutDialog", u"git fetch --prune: update the remote branches. Changes nothing in your working tree.", None))
#endif // QT_CONFIG(tooltip)
        self.label_commits.setText(QCoreApplication.translate("CheckoutDialog", u"Commits on this branch, newest first", None))
        ___qtablewidgetitem = self.tableWidget_commits.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("CheckoutDialog", u"Commit", None))
        ___qtablewidgetitem1 = self.tableWidget_commits.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("CheckoutDialog", u"Date", None))
        ___qtablewidgetitem2 = self.tableWidget_commits.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("CheckoutDialog", u"Message", None))
        ___qtablewidgetitem3 = self.tableWidget_commits.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("CheckoutDialog", u"Pipeline", None))
        self.label_checkoutError.setText("")
        self.label_checkoutNote.setText(QCoreApplication.translate("CheckoutDialog", u"Checkout is refused while the repo has local changes. Commit or stash them yourself first; WFlash never discards or stashes your work.", None))
        self.label_checkoutStatus.setText("")
        self.pushButton_cancelCheckout.setText(QCoreApplication.translate("CheckoutDialog", u"Cancel", None))
        self.pushButton_checkout.setText(QCoreApplication.translate("CheckoutDialog", u"Checkout", None))
    # retranslateUi


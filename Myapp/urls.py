
from django.urls import path
from.views import *
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('refresh-token/',CustomTokenRefreshVieuw.as_view(), name='token_refresh'),
    path('login/',LoginView.as_view(), name='login' ),
    path('user/create/', UserCreateView.as_view(), name='user_create'),
    path('user/liste/',ListeUserView.as_view(), name ='user_liste'),
    path('user/detail/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('user/<int:pk>/delete/', UserDeleteView.as_view(), name='delete_user'),
    path('UpdateUser/<int:id>/',UpdateUserView.as_view(), name='update_user'),
    path('change-password/', ChangePasswordView.as_view(), name='changer_mot de passe'),
    #envoi de mot de mots de passe de réinitialisation
    path('passwordRequest/',PasswordResetRequestView.as_view(), name='password_reste_request'),

    path('password-reset-confirm/',PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    #routes pour le suppléants
    path('substituteCreate/',CreateSubstituteView.as_view(), name='substute'),
    path('ListeSubstitute/', ListeSubstituteView.as_view(), name='liste_substitute'),
    path('subdstitute/delete/<int:id>/',DeleteSubstituteView.as_view(), name= 'substitute_delete'),
    path('substituteUpdate/<int:pk>/', UpdateSubstituteView.as_view(), name='substitute-update'),
    #fin des routes pour le suppléants 
    #route pour le depôt et retraint
    path('adminDeposit/', AdminDepositView.as_view(), name='admin-deposit'),
    path('adminWithdraw/', AdminWithdrawView.as_view(), name='admin-withdraw'),
    path('adminDepositSocial/', AdminDepositSocial.as_view(), name = 'admin-deposit-social'),
    #fin route pour depôt et retrait
    path('userTransaction/<int:user_id>/', UserTransactionListByIdView.as_view(), name='list_transaction'),
    path('transactionList/',TransactionListView.as_view(), name='liste-transaction'),
    path('sendMoney/', SendMoneyView.as_view(), name='send_money'),
    path('transations/cancel/<int:pk>/', CancelTransactionViews.as_view(), name='annuler_transaction'),

    # route pour la creation du credit 
    path('credits/create/', CreditCreateView.as_view(), name= "credit_create"),
    path("creditsRepay/", CreditRepaymentView.as_view(), name="credit_repay"),
    path('ListCredit/', CreditListViews.as_view(), name='list-credit'),
    path('ListeTrasCreditRemboursement/', CreditTransactionListView.as_view(), name='transaction_credit_remboursement'),
    path('UserListeTransactionRemboursement/<int:user_id>/', UserCreditTransactionView.as_view(), name='user_transaction_credit'),
    path('userCredit/<int:user_id>/', UserCreditView.as_view(), name ='user_credit'),
    path('CreditTransaction/cancel/<int:pk>/', CancelCreditTransaction.as_view(),name='cancel_transaction_credit'),
    # fin
    #route pour le cashout Detail
    path('cashout/create/', CreateCashoutViews.as_view(), name='create_cashout'),
    path('cashout/liste/', CashOutViews.as_view(), name='cashout-liste'),
    path('cashoutDetail/', CashOutDetailViews.as_view(), name='cashout-detail'),
    path('cashoutDelete/<int:id>/', DeleteCashout.as_view(), name='delete_cashout'),

    #route pour le cycle 
    path('cycles/', CycleListCreateView.as_view(), name='cycle-list-create'),
    path('cycles/<int:pk>/', CycleDetailView.as_view(), name='cycle-detail'),
    path('cycleUpdate/<int:pk>/',CycleDetailView.as_view(), name='update_cycle'),
    
    #routes pour le code PIN
    path('user/set-pin/', SetPinView.as_view(), name='set-pin'),
    path('user/change-pin/', ChangePinView.as_view(), name='change-pin'),
    path('user/verify-pin/', VerifyPinView.as_view(), name='verify-pin'),

]


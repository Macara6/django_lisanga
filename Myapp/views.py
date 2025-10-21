from django.shortcuts import render
from django.template import loader
from django.http import HttpResponse
from django.contrib.auth import authenticate
import random
from django.core.mail import send_mail
from rest_framework import status
from rest_framework import generics, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import RetrieveDestroyAPIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAdminUser
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from .serializers import *
from .models import *
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import Sum, Prefetch
User = get_user_model()




def index(request):
    template = loader.get_template("index.html")
    context = {}
    return HttpResponse(template.render(context, template))


class CustomTokenRefreshVieuw(TokenRefreshView):
    permission_classes = []
    def post (self, request, *args, **kwargs):
        serializers = TokenRefreshSerializer(data = request.data)
        serializers.is_valid(raise_exception=True)
        
        return Response({
            'token': serializers.validated_data['access']
        }, status= status.HTTP_200_OK)
    
class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password = password)
        if user is None:
            return Response({'error':'Compté non trouvé ou identifiants invalides'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if user.is_superuser:
            token = RefreshToken.for_user(user)
            return Response({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'token': str(token.access_token),
                'is_superuser': user.is_superuser
            }, status=status.HTTP_200_OK)

        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'id':user.id,
                'username':user.username,
                'email':user.email,
                'token': str(refresh.access_token),
                'refresh':str(refresh)
            },status=status.HTTP_200_OK)



#ddebut views pour l'utilisateur
class UserCreateView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [IsAuthenticated]


class ListeUserView(generics.ListAPIView):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = userViewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        return(
            User.objects.all().select_related("substitute").prefetch_related(
                Prefetch(
                    "credits",
                    queryset=Credit.objects.filter(is_paid=False).only(
                        "princilal", "total_due", "balance_due", "is_paid", "user_id"
                    ),
                    to_attr="unpaid_credits"
                )
            )
            .annotate(
                total_principal_unpaid=Sum("credits__princilal", filter=~models.Q(credits__is_paid=True)),
                total_due_unpaid=Sum("credits__total_due", filter=~models.Q(credits__is_paid=True)),
                total_balance_due_unpaid=Sum("credits__balance_due", filter=~models.Q(credits__is_paid=True)),
            )
            .order_by("-date_joined")
        )


class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = userViewSerializer
    permission_classes = [IsAuthenticated]

    def get(self,request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

class UpdateUserView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = userViewSerializer
    permission_classes = [IsAuthenticated]
    lookup_field ='id'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context
    

class UserDeleteView(generics.DestroyAPIView):
    queryset = User.objects.all()
    serializer_class= userViewSerializer
    permission_classes = [IsAuthenticated]
    
    def delete(self, request,*args, **kwargs):
        try:
            user = self.get_object()
            username = user.username
            user.delete()
            return Response(
                {"message": f"L'utilisateur '{username}' a été supprimé avec succès."},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
#fin des views pour la gestion des utilisateurs 

# debut des views pour le suppléant
class CreateSubstituteView(generics.CreateAPIView):
    queryset = Substitute.objects.all()
    serializer_class =CreateSubstuteSerialize
    permission_classes = [IsAuthenticated]

class ListeSubstituteView(generics.ListAPIView):
    queryset = Substitute.objects.all()
    serializer_class = CreateSubstuteSerialize
    permission_classes = [IsAuthenticated]

class UpdateSubstituteView(generics.RetrieveUpdateAPIView):
    queryset = Substitute.objects.all()
    serializer_class = CreateSubstuteSerialize
    permission_classes = [IsAuthenticated]

class DeleteSubstituteView(RetrieveDestroyAPIView):
    queryset = Substitute.objects.all()
    serializer_class = CreateSubstuteSerialize
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
# fin des views pour le suppléant 

#debut views pour la gestion du depôt et retrait
class AdminDepositView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    def post(self,request,*args, **kwargs):
        serializer = DepositByMatriculeSerializer(data= request.data, context={'request':request})
        serializer.is_valid(raise_exception=True)
        transaction  = serializer.save()
        
        send_user_update(
            transaction.user.id,
            event_type="deposit",
            message="Dépôt effectué avec succès"
        )
        return Response(TransactionSerializer(transaction).data)
    

    
class AdminWithdrawView(APIView):
    authentication_classes =[JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    
    def post(self, request, *args, **kwargs):
        serializer = WithdrawByMatriculeSerializer(data=request.data, context={'request':request})
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()

        send_user_update(
            transaction.user.id,
            event_type='withdraw',
            message=f"Retrait de {transaction.amount} effectué avec succès"
        )
        return Response(TransactionSerializer(transaction).data)
    
class AdminDepositSocial(APIView):
    authentication_classes =[JWTAuthentication]
    permission_classes =[permissions.IsAdminUser]
    
    def post(self, request, *args, **kwargs):
        serializer = DepositSocialSerialize(data = request.data, context ={'request':request})
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        
        send_user_update(
            transaction.user.id,
            event_type='social',
            message='Dépôt soicial effectué avec succeès'
        )
        
        return Response(TransactionSerializer(transaction).data)
#fin de view pour le depôt et retrait 

class UserTransactionListByIdView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id, *args, **kwargs):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"detail": "Utilisateur non trouvé."}, status=404)
        
        transactions = Transaction.objects.filter(user=user).order_by('-created_at')
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)

class TransactionListView(generics.ListAPIView):
    queryset = Transaction.objects.all().order_by('-created_at')
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

#view send money 
class SendMoneyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SendMoneyByMatriculeSerializer(data=request.data, context={'request':request})
        if serializer.is_valid():
            result = serializer.save()
            
            sender_transaction = result["sender_transaction"]
            recipient_transaction = result["recipient_transaction"]
            balances = result["balances"]

            #Envoi de mise à jour WebSocket à l'expéditeur
            send_user_update(
                sender_transaction.user.id,
                event_type='send',
                message='Envoie effectué avec succès',
                extra_data ={
                     'amount': float(sender_transaction.amount),
                     'balance': float(sender_transaction.balance_after)
                }
                
            )
           
            #envoie de mise à jour au destinateur
            send_user_update(
                recipient_transaction.user.id,
                event_type='receive',
                message=f'Vous avez reçu {recipient_transaction.amount} USD de {sender_transaction.user.first_name}',
                extra_data ={
                     'amount': float(recipient_transaction.amount),
                     'balance': float(recipient_transaction.balance_after)
                }
            )
          
            return Response({
                "message": "Envoi effectué avec succès ",
                "sender_transaction": str(result["sender_transaction"]),
                "recipient_transaction": str(result["recipient_transaction"]),
                "balances": balances
            },status=201)
        return Response(serializer.errors, status=400)


#views pour annuler la tansation
class CancelTransactionViews(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
           tx = Transaction.objects.get(pk=pk)
           reverse_tx = tx.cancel()
           if tx.user.email:
                message = (
                    f"Bonjour {tx.user.first_name},\n\n"
                    f"Votre transaction d'un montant de {tx.amount} a été annulée avec succès.\n\n"
                    f"Transaction inverse : {reverse_tx.reference}\n"
                    f"Merci,\n"
                    f"L'équipe de gestion"
                )

                send_mail(
                    subject="Annulation de votre transaction",
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[tx.user.email],
                    fail_silently=False,
                )
                
           return Response({
               "message": "Transaction annulée",
               "reverse_transaction": reverse_tx.id
           },status=status.HTTP_200_OK)
        except Transaction.DoesNotExist:
            return Response({"error": "Transaction introuvable"}, status=404)
        except Exception as e:
            return Response({"error":str(e)}, status=400)


#view pour le credit
class CreditCreateView(APIView):
    """
    Créer un crédit pour un utilisateur via son matricule
    """
    def post(self,request, *args, **kwargs):
        serializer = CreditCreateSerializer(data= request.data)
        if serializer .is_valid():
            credit = serializer.save()
            return Response({
                "message": "Crédit créé avec succès",
                "credit_id":credit.id,
                "total_due":credit.total_due,
                "balance_due":credit.balance_due,
                "due_date":credit.due_date
            },status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class CreditRepaymentView(APIView):
    """
    Effectuer un remboursement sur un crédit
    """
    def post(self, request, *args, **kwargs):
        print("RAW DATA:", request.data)
        serializer = CreditRepaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        credit = serializer.save()

        return Response({
            "message": "Remboursement effectué avec succès.",
            "balance_due": credit.balance_due,
            "is_paid": credit.is_paid,
        })

# crédit pour un utilisateur
class UserCreditView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, user_id, *args, **kwargs):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"Detail":"Utilisateur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        credits = Credit.objects.filter(user = user).order_by('-created_at')
        serializer = CreditSerializer(credits, many =True)
        return Response(serializer.data)
    
#liste credit 
class CreditListViews(generics.ListAPIView):
    queryset = Credit.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    serializer_class = CreditSerializer

class CreditTransactionListView(generics.ListAPIView):
    queryset = CreditTransaction.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    serializer_class = CreditTransactionSerializer

class UserCreditTransactionView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, user_id, *args, **kwargs):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"detail":"Utilisateur non trouvé"}, status=404)
        
        transaction = CreditTransaction.objects.filter(credit__user=user).order_by('-created_at')
        serializer = CreditTransactionSerializer(transaction, many=True)
        return Response(serializer.data)

#views pour annuler la trasaction credit et remboursement
class CancelCreditTransaction(APIView):
    permission_classes =[IsAuthenticated]

    def post(self, request, pk):
        try:
            tx = CreditTransaction.objects.get(pk=pk)
            
            reverse_tx = tx.cancel()
       
            return Response({
                "message":"Transaction annulée",
                "reverse_transaction":reverse_tx.id
            },status=status.HTTP_200_OK)
        except CreditTransaction.DoesNotExist:
            return Response({"error":"Transaction introuvable"}, status=404)
        except Exception as e:
            return Response({"error":str(e)}, status=400)

#views  pour la creation de bon de sortie 
class CreateCashoutViews(generics.CreateAPIView):
    queryset = CashOut.objects.all()
    permission_classes =[IsAuthenticated]
    serializer_class = CashOutCreateSerializer

class CashOutViews(generics.ListAPIView):
    serializer_class = CashOutSerialier
    permission_classes =[IsAuthenticated]
    queryset = CashOut.objects.all().order_by('-created_at')

class CashOutDetailViews(generics.ListAPIView):
    serializer_class = CashOutetailSerializer
    permission_classes =[IsAuthenticated]

    def get_queryset(self):
        cashout_id = self.request.query_params.get('cashout')

        if cashout_id:
            return CashOutDetail.objects.filter(cashout__id = cashout_id)
        return CashOutDetail.objects.none()


class DeleteCashout(RetrieveDestroyAPIView):
    queryset = CashOut.objects.all()
    permission_classes =[IsAuthenticated]
    serializer_class = CashOutCreateSerializer
    lookup_field ='id'
   

class CycleListCreateView(APIView):
    """Lister tous les cycles et créer un nouveau cycle"""
    
    def get(self, request):
        cycles = Cycle.objects.all()
        serializer = CycleSerializer(cycles, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = CycleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class CycleDetailView(APIView):
    """Récupérer, modifier ou supprimer un cycle par ID"""
    
    def get(self, request, pk):
        cycle = get_object_or_404(Cycle, pk=pk)
        serializer = CycleSerializer(cycle)
        return Response(serializer.data)
    
    def put(self, request, pk):
        cycle = get_object_or_404(Cycle, pk=pk)
        serializer = CycleSerializer(cycle, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        cycle = get_object_or_404(Cycle, pk=pk)
        serializer = CycleSerializer(cycle, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        cycle = get_object_or_404(Cycle, pk=pk)
        cycle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
#views pour changer le mot de passe 
class ChangePasswordView(APIView):
    permission_classes =[IsAuthenticated]
    def post(self, request, *args, **kwargs):
        serializer= ChangerPasswordSerialier(data=request.data, context={'request':request})
        if serializer.is_valid():
            serializer.save()
            return Response({"detail":"Mot de passe changé avec succès."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#views pour générer et envoyer le code
class PasswordResetRequestView(APIView):
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email =serializer.validated_data['email']
       
        try:
             user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"email":["Aucun utilisateur avec ce email"]}, status=400)
        
        code = f"{random.randint(100000,999999)}"
        PasswordResetCode.objects.create(user=user, code=code)
        message =(
             f"Bonjour {user.username},\n\n"
             f"Votre code de réinitialisation est : {code}\n\n "
             "Ce code expire dans 15 minutes.\n\n"
             "Si vous n'avez pas demandé cette réinitialisation, ignorez cet email."
        )
        send_mail(
            subject='Réinitialisation du mot de passe',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        return Response({"detail":"code envoyé à l'email."},status=status.HTTP_200_OK)
    
# confirmer le code et définir le mot de passe
class PasswordResetConfirmView(APIView):
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail":"Mot de passe réinitilisé avec succès"}, status=status.HTTP_200_OK)


#fonction pour le channel
def send_user_update(user_id, event_type="update", message="Mise à jour du compte", extra_data = None):
    """
    Envoie une mise à jour en temps réel à un utilisateur via WebSocket,
    incluant le solde et les dernières transactions.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:10]
    transaction_data = TransactionSerializer(transactions, many=True).data

    data = {
        "event":event_type,
        "message":message,
        "user_id":user.id,
        "balance":float(user.balance),
        "social":float(user.social),
        "transactions":transaction_data,
    }

    if extra_data:
        data.update(extra_data)

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",  
        {
            "type": "user_update",
            "data": data,  
        }
    )



# --- Vues pour la gestion du code PIN ---

class SetPinView(APIView):
    """Définir un code PIN (si non encore défini)"""
    permission_classes = [IsAuthenticated]

    def post(self,request):
        serializer = SetPinSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Code PIN défini avec succès."}, status=status.HTTP_200_OK)
    

class ChangePinView(APIView):
    """Modifier le code PIN"""
    permission_classes= [IsAuthenticated]
    
    def post(self,request):
        serializer = ChangePinSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail":"Code PIN modifié avec succès."}, status=status.HTTP_200_OK)

class VerifyPinView(APIView):
    """ Vérifier si un code PIN est correct """
    
    def post(self, request):
        serializer = VerifyPinSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response({"detail": "Code PIN correct."}, status=status.HTTP_200_OK)
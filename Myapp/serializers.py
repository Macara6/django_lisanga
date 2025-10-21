
from rest_framework import serializers
from django.contrib.auth import get_user_model
User = get_user_model() 
from .models import *
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Sum



class UserCreateSerializer(serializers.ModelSerializer):
     class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'adress',
            'substitute',
            'matricule',
            'password',
            'date_joined',
            'created_by',
        ]
        extra_kwargs = {
            'password':{'write_only':True},
            'date_joined':{'read_only':True}
        }
    
     def validate_email(self,value):
         """Vérifie  si l'email existe déjà"""
         if User.objects.filter(email=value).exists():
             raise serializers.ValidationError("Cet email est déjà utiliser pour un autre utilisateur")
         return value

     def validate_username(self, value):
        """Vérifie qu'il n'y a pas d'espace dans le username."""
        if ' ' in value:
            raise serializers.ValidationError("Le nom d'utilisateur ne doit pas contenir d'espaces.")
        return value
        

     def validate_matricule(self, value):
          """Vérifie que le matricule n'est pas déjà utilisé."""
          if User.objects.filter(matricule=value).exists():
              raise serializers.ValidationError("Ce matricule est déjà utiliser pour un autre utilisateur")
          return value
     
     
     def create(self, validated_data):
         password = validated_data.pop('password')
         user = User(**validated_data)
         user.set_password(password)
         user.save()
         return user

class userViewSerializer(serializers.ModelSerializer):

    substitute_name = serializers.CharField(source='substitute.first_name', read_only=True)
    total_interest_user = serializers.SerializerMethodField()

    total_principal_unpaid = serializers.SerializerMethodField()
    total_due_unpaid = serializers.SerializerMethodField()
    total_balance_due_unpaid = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'adress',
            'substitute',
            'substitute_name',
            'balance',
            'social',
            'matricule',
            'date_joined',
            'is_superuser',
            'total_interest_user',
            'total_principal_unpaid',
            'total_due_unpaid',
            'total_balance_due_unpaid',
        ]
    def get_total_interest_user(self, obj):
        """
        Calcule la part d’intérêt attribuée à cet utilisateur.
        """
        total_due = Credit.objects.aggregate(Sum("total_due"))["total_due__sum"] or Decimal("0.0")
        if total_due == 0:
            return Decimal("0.0")

        # 10% du total des crédits = intérêt global
        total_interest = total_due * Decimal("0.10")

        # 90% après dîme (10%)
        net_interest = total_interest * Decimal("0.90")

        total_balance = User.objects.aggregate(Sum("balance"))["balance__sum"] or Decimal("0.0")
        if total_balance == 0:
            return Decimal("0.0")

        user_interest = (obj.balance * net_interest) / total_balance
        return round(user_interest, 2)
    
    def _get_unpaid_totals(self, obj):
        
        if not hasattr(self, '_unipaid_cache'):
            self._unipaid_cache ={}

        if obj.id not in self._unipaid_cache:
            aggregates = obj.credits.filter(is_paid=False).aggregate(
                total_principal = Sum('princilal'),
                total_due = Sum('total_due'),
                total_balance_due =Sum('balance_due')
            )

            self._unipaid_cache[obj.id] ={
                'total_principal_unpaid': aggregates['total_principal'] or 0,
                'total_due_unpaid': aggregates['total_due'] or 0,
                'total_balance_due_unpaid': aggregates['total_balance_due'] or 0,
            }
        return self._unipaid_cache[obj.id]

    def get_total_principal_unpaid(self, obj):
        return self._get_unpaid_totals(obj)['total_principal_unpaid']
    
    def get_total_due_unpaid(self, obj):
        return self._get_unpaid_totals(obj)['total_due_unpaid']
    
    def get_total_balance_due_unpaid(self, obj):
        return self._get_unpaid_totals(obj)['total_balance_due_unpaid']
    
    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.context['request'].user
        if user.is_superuser:
            for field in ['phone_number', 'adress', 'matricule', 'substitute']:
                self.fields[field].required = False

class CreateSubstuteSerialize(serializers.ModelSerializer):
    class Meta:
        model = Substitute
        fields = [
            'id',
            'first_name',
            'last_name',
            'phone_number',
            'email',
            'adress',
        ] 

class TransactionSerializer(serializers.ModelSerializer):
    compte_name = serializers.CharField(source = 'user.first_name', read_only = True)
    class Meta:
        model = Transaction
        fields = ['id', 'user', 'transaction_type', 'amount', 'balance_after', 'reference','compte_name' ,'created_at']
        read_only_fields = ['id', 'user', 'balance_after', 'reference', 'created_at']

class CreditSerializer(serializers.ModelSerializer):
    compte_name = serializers.CharField(source = 'user.first_name', read_only = True)
    class Meta:
        model = Credit
        fields =['id','princilal','total_due','balance_due','interset_rate','compte_name','is_paid', 'due_date', 'created_at']

#serializer transaction credit et remboursement      
class CreditTransactionSerializer(serializers.ModelSerializer):
    compte_name = serializers.CharField(source ='credit.user.first_name')
    balance_due = serializers.DecimalField( source ='credit.balance_due',max_digits=12, decimal_places=2,)
    user = serializers.IntegerField(source ='credit.user.id',read_only=True)
    class Meta:
        model = CreditTransaction
        fields =['id','credit','transaction_type','amount','reference','user','compte_name','balance_due','created_at']

#serializer pour faire le depôt de le compte 
class DepositByMatriculeSerializer(serializers.Serializer):
      matricule = serializers.CharField(max_length=100)
      amount = serializers.DecimalField(max_digits=12, decimal_places=2)
      def validate_amount(self, value):
          if value <=0:
            raise serializers.ValidationError("Le montant du dépôt doit être positif.")
          return value
      def validate_matricule(self, value):
            try:
                user = CustomUser.objects.get(matricule=value)
                self.context['user_target'] = user
            except CustomUser.DoesNotExist:
                raise serializers.ValidationError("Utilisateur introuvable avec ce matricule.")
            return value

      def save(self, **kwargs):
          user_target = self.context.get('user_target')
          amount =  self.validated_data['amount']
          user_target.deposit(amount)
          transaction = Transaction.objects.filter(user=user_target).latest('created_at')
          #prepation du mail
          subject = 'Dépôt épargne sur votre compte Lisanga ✅'
          message = (
              f"Bonjour {user_target.first_name},\n\n"
              f"Un dépôt épargne a été effectué sur votre compte.\n\n"
              f"--- Détails de la transaction ---\n"
              f"Référence : {transaction.reference}\n"
              f"Montant : {transaction.amount} USD\n"
              f"Type : {transaction.transaction_type}\n"
              f"Nouveau solde : {transaction.balance_after} USD\n"
              f"Date : {transaction.created_at.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
              f"Merci de votre confiance."
          )
          from_email = settings.DEFAULT_FROM_EMAIL
          recipient_list = [user_target.email]
          send_mail(subject, message, from_email, recipient_list, fail_silently=False)
          return transaction
      
#serilizer pour faire le retrait
class  WithdrawByMatriculeSerializer(serializers.Serializer):
    matricule = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    def validate_amount(self, value):
        if value <=0:
            raise serializers.ValidationError("Le montant du retrait doit être positif.")
        return value
    
    def validate_matricule(self, value):
        try:
            user = CustomUser.objects.get(matricule = value)
            self.context['user_target'] = user
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Utilisateur introuvable avec ce matricule.")
        return value
    def save(self,**kwargs):
        user_target = self.context['user_target']
        amount = self.validated_data['amount']
        if user_target.balance < amount:
            raise serializers.ValidationError("Solde insuffisant pour ce retrait.")
        user_target.withdraw(amount)
        transaction = Transaction.objects.filter(user=user_target).latest('created_at')
        #preparation email
        subject ='Retrait épargne sur votre compte Lisanga'

        message =(
            f"Bonjour {user_target.first_name},\n\n"
            f"Un retrait épargne a été effectué sur votre compte.\n\n"
            f"Référence : {transaction.reference}\n"
            f"Montant : {transaction.amount} USD\n"
            f"Type : {transaction.transaction_type}\n"
            f"Nouveau solde : {transaction.balance_after} USD\n"
            f"Date : {transaction.created_at.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"Merci de votre confiance."  
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_target.email],
            fail_silently=False

        )
        return transaction
    
class SendMoneyByMatriculeSerializer(serializers.Serializer):
    matricule = serializers.CharField(max_length=100)  # corrigé
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant d'envoi doit être positif")
        return value

    def validate_matricule(self, value):   # corrigé
        try:
            recipient = CustomUser.objects.get(matricule=value)
            self.context['recipient'] = recipient
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Aucun utilisateur trouvé avec ce matricule")
        return value
    
    def save(self, **kwargs):
        sender = self.context['request'].user
        recipient = self.context['recipient']
        amount = self.validated_data['amount']   # corrigé: validated_data

        if sender.balance < amount:
            raise serializers.ValidationError("Solde insuffisant pour effectuer l'envoi")
        
        result = sender.send_money(recipient, amount)
        sender_transaction = Transaction.objects.filter(user=sender).latest('created_at')
        recipient_transaction = Transaction.objects.filter(user=recipient).latest('created_at')

        # notification email
        subject = "Vous avez reçu un envoi d'argent 💸"
        message = (
            f"Bonjour {recipient.first_name},\n\n"
            f"Vous avez reçu un envoi d'argent de la part de {sender.first_name}.\n\n"
            f"--- Détails de la transaction ---\n"
            f"Référence : {recipient_transaction.reference}\n"
            f"Montant : {recipient_transaction.amount} USD\n"
            f"Type : {recipient_transaction.transaction_type}\n"
            f"Nouveau solde : {recipient_transaction.balance_after} USD\n"
            f"Date : {recipient_transaction.created_at.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"Merci d'utiliser notre service."
        )

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient.email],
            fail_silently=False
        )
        subject_sender = "Confirmation de votre envoi d'argent ✅"
        message_sender = (
            f"Bonjour {sender.first_name},\n\n"
            f"Vous avez envoyé {amount} USD à {recipient.first_name} {recipient.last_name} ({recipient.matricule}).\n\n"
            f"--- Détails de la transaction ---\n"
            f"Référence : {sender_transaction.reference}\n"
            f"Montant : {sender_transaction.amount} USD\n"
            f"Type : {sender_transaction.transaction_type}\n"
            f"Nouveau solde : {sender_transaction.balance_after} USD\n"
            f"Date : {sender_transaction.created_at.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"Merci d'utiliser notre service."
        )

        send_mail(
            subject_sender,
            message_sender,
            settings.DEFAULT_FROM_EMAIL,
            [sender.email],
            fail_silently=False
        )

        return {
            "sender_transaction": sender_transaction,
            "recipient_transaction": recipient_transaction,
            "balances": result   # harmonisé avec ta view
        }


class DepositSocialSerialize(serializers.Serializer):
    matricule = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_amount(self, value):
        if value <=0:
            raise serializers.ValidationError("le montant social doit être positive")
        return value
    def validate_matricule(self, value):
        try:
            user = CustomUser.objects.get(matricule = value)
            self.context['user_target'] = user
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Utilisateur introuvable avec ce matricule")
        return value
    def save(self,**kwargs):
        user_target = self.context.get('user_target')
        amount = self.validated_data['amount']
        user_target.deposit_social(amount)
        transaction = Transaction.objects.filter(user = user_target).latest('created_at')

        subject ='Dépôt sociale sur votre compte ✅'
        message =(
            f"Bonjour {user_target.first_name},\n\n"
            f"Un dépôt social a été effectué sur votre compte.\n\n"
            f"Référence : {transaction.reference}\n"
             f"Montant : {transaction.amount} USD\n"
            f"Type : {transaction.transaction_type}\n"
            f"Nouveau solde : {transaction.balance_after} USD\n"
            f"Date : {transaction.created_at.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"Merci de votre confiance." 

        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_target.email],
            fail_silently=False
        )
        return transaction

# serializer  transaction credit 
class CreditCreateSerializer(serializers.ModelSerializer):
    matricule = serializers.CharField(write_only = True)
    class Meta:
        model = Credit
        fields = ['matricule','princilal','interset_rate','due_date']
        read_only_fields = ['total_due', 'balance_due', 'is_paid', 'created_at']

    def validate_princilal(self, value):
        if value <= 0:
            raise ValueError("Le montant doit être positif")
        return value
    def validate_itnterest_rate(self, value):
        if value < 0:
            raise ValueError("Le taux d'intérêt doit être positif.")
        return value
    def create(self, validated_data):
        matricule = validated_data.pop('matricule')
        
        try:
            user = CustomUser.objects.get(matricule = matricule)
        except CustomUser.DoesNotExist:
            raise ValueError({"matricule":"Utilisateur non trouvé."})
        
        credit = Credit.objects.create(
            user = user,
            **validated_data
        )
        CreditTransaction.objects.create(
            credit = credit,
            transaction_type = 'CREDIT', 
            amount = credit.princilal
        )
        transaction = CreditTransaction.objects.filter(credit__user=user).latest('created_at')

        message = (
            f"Bonjour {user.first_name},\n\n"
            f"Votre demande de crédit d'un montant de {credit.princilal} USD a été approuvée avec succès.\n\n"
            f"-------Détails du crédit------\n"
            f"Montant emprunté : {credit.princilal} USD\n"
            f"Montant total à rembourser : {credit.total_due} USD\n"
            f"Date limite de remboursement : {credit.due_date}\n"
            f"Taux d’intérêt : {credit.interset_rate * 100}%\n\n"
            f"Référence : {transaction.reference}\n"
            f"Merci de respecter les échéances pour éviter tout frais supplémentaire."
        )
        subject = "Confirmation de votre crédit"

        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list =[user.email]
        try:
          send_mail(subject,message, from_email, recipient_list, fail_silently=False)
        except Exception as e:
            print("Erreur lors de l'envoi de l'email:", e)
        return credit
    
class CreditRepaymentSerializer(serializers.Serializer):
    credit_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    def validate(self, data):
        try:
            credit = Credit.objects.get(id=data["credit_id"])
        except Credit.DoesNotExist:
           raise serializers.ValidationError({"credit_id":"Crédit introuvable"})
        if credit.is_paid:
            raise serializers.ValidationError("Ce crédit est déjà entièrement remboursé")
        
        data["credit"]= credit
        return data

    def create(self, validate_data):
        credit = validate_data["credit"]
        amount = Decimal(validate_data["amount"])

        credit.make_repayement(amount)

        CreditTransaction.objects.create(
            credit = credit,
            transaction_type = "REMBOURSEMENT",
            amount = amount 
        )
        
        user = credit.user
        transaction = CreditTransaction.objects.filter(credit__user=user).latest('created_at')
        message = (
            f"Bonjour {user.first_name},\n\n"
            f"Nous confirmons la réception de votre remboursement pour le crédit en cours.\n\n"
            f"-------Détails du remboursement------\n"
            f"Montant remboursé : {amount} USD\n"
            f"Montant restant à rembourser : {credit.balance_due} USD\n"
            f"Crédit total initial : {credit.total_due} USD\n"
            f"Date limite de remboursement : {credit.due_date}\n\n"
            f"Référence : {transaction.reference}\n"
            f"Merci pour votre paiement. Veuillez continuer à respecter les échéances pour éviter tout frais supplémentaire."
        )
        send_mail(
            subject="Confirmation de remboursement",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        return credit

#class pour le bon de sortie 
class CashOutetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashOutDetail
        fields =['id','reason','amount']

class CashOutSerialier(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = CashOut
        fields = ['id','user','user_name','created_at','motif','total_amount']

class CashOutDatailCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashOutDetail
        fields = ['reason', 'amount']

class CashOutDetailReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashOutDetail
        fields = ['id', 'reason', 'amount']

class UserCashOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']  

class CashOutCreateSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), write_only=True, source='user'
    )
    
    details = serializers.SerializerMethodField(read_only=True)
    
    detail_inputs = CashOutDatailCreateSerializer(many=True, write_only=True, source='details')
    
    class Meta:
        model = CashOut
        fields = ['user_id','motif', 'total_amount', 'details', 'detail_inputs']
    
    def get_details(self, obj):
        return CashOutDetailReadSerializer(obj.details.all(), many=True).data

    def create(self, validated_data):
        details_data = validated_data.pop('details', [])
        cashout = CashOut.objects.create(**validated_data)
        for detail in details_data:
            CashOutDetail.objects.create(cashout=cashout, **detail)
        return cashout
# fin des classes pour la creation de bon de sortie

#serializer pour le cycle
class CycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cycle
        fields = ["id", "name", "start_date", "end_date", "is_active"]

    def validate(self,data):
        """Vérifie que la date de fin est après la date de début"""
        start_date = data.get("start_date",getattr(self.instance, "start_date", None))
        end_date = data.get("end_date", getattr(self.instance, "end_date", None))

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError("La date de fin doit être postérieure à la date de début.")
        return data
    
# modifeir le mot de passe 
class ChangerPasswordSerialier(serializers.Serializer):
    old_password =serializers.CharField(required=True,write_only=True)
    new_password= serializers.CharField(required=True, write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("L'ancien mot de passe est incorrect")
        return value
    
    def validate_new_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError("le nouveau mot de passe doit contenir au moins 6 caractères")
        return value
    
    def save(self,**kwargs):
        user = self.context['request'].user
        new_password = self.validated_data['new_password']
        user.set_password(new_password)
        user.save()
        return user

#serializer pour le mot de passe oublier 
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Aucun utilisateur utilise cet email")
        return value
#serializer pour vérifier le code et réinitialiser le mot de passe
class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only =True)

    def valide(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        if len(attrs['new_password']) < 6:
            raise serializers.ValidationError("Le mots de passe doit contenir aumoins 6 caractères.")
        return attrs

    def save(self):
        email = self.validated_data['email']
        code = self.validated_data['code']
        new_password = self.validated_data['new_password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Aucun utilisateur tourvé avec cet email")
        
        try:
            reset_code = PasswordResetCode.objects.get(user=user, code=code, is_used=False)
        except PasswordResetCode.DoesNotExist:
            return serializers.ValidationError("code invaide")

        if not reset_code.is_valid():
            raise serializers.ValidationError("le code est éxpiré")

        user.set_password(new_password)
        user.save()

        reset_code.is_used=True
        reset_code.save() 

class SetPinSerializer(serializers.Serializer):

    pin = serializers.CharField(write_only=True)  

    def validate_pin(self, value):
        if not value.isdigit() or len(value) not in [4,6]:
            raise serializers.ValidationError("Le code PIN doit contenir 4 ou 6 chiffres.")
        return value

    def create(self, validate_data):
        user = self.context['request'].user
        user.set_pin(validate_data['pin'])
        return user

class ChangePinSerializer(serializers.Serializer):
    old_pin = serializers.CharField(write_only=True)
    new_pin = serializers.CharField(write_only=True) 

    def validate(self, data):
        user = self.context['request'].user
        if not user.check_pin(data['old_pin']):
            raise serializers.ValidationError({"old_pin": "Ancien code PIN incorrect."})
        if not  data['new_pin'].isdigit() or len(data['new_pin']) not in [4, 6]:
            raise serializers.ValidationError({"new_pin": "Le code PIN doit contenir 4 ou 6 chiffres."})
        return data
    
    def save(self):
        user = self.context['request'].user
        user.set_pin(self.validated_data['new_pin'])
        return user
    
class VerifyPinSerializer(serializers.Serializer):
    pin = serializers.CharField(write_only=True)

    def validate(self, data):
        user = self.context['request'].user
        if not user.check_pin(data['pin']):
            raise serializers.ValidationError({"pin": "Code PIN incorrect."})
        return data
    



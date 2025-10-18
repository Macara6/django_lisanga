from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.db import transaction as db_transaction
import datetime
from django.db.models import Sum
from django.contrib.auth.hashers import make_password, check_password



class Substitute(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    adress = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class CustomUser(AbstractUser):
    created_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='created_users'
    )
    phone_number = models.CharField(max_length=100)
    adress = models.CharField(max_length=100)
    matricule = models.CharField(max_length=100, unique=True)
    substitute = models.ForeignKey(
        "Substitute", null=True, blank=True, on_delete=models.SET_NULL, related_name='users'
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    social = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    pin_code = models.CharField(max_length=128, blank=True, null=True)

    def __str__(self):
        return f"{self.username}"

    def set_pin(self, pin:str):
        """Définit un code PIN sécurisé (haché)"""
        if not pin.isdigit() or len(pin) not in [4,6]:
            raise ValueError("Le code PIN doit être composé de 4 ou 6 chiffres.")
        self.pin_code = make_password(pin)
        self.save()

    def check_pin(self, pin:str) -> bool:
         """Vérifie si le code PIN saisi correspond"""
         if not self.pin_code:
             return False
         return check_password(pin, self.pin_code)
    
    def rest_pin(self, new_pin:str):
         """Réinitialise le code PIN"""
         self.set_pin(new_pin)

    @property
    def total_interest_user(self):
        """Renvoie la part d'intérêt attribuée à cet utilisateur"""
        from .models import Credit
        total_principal = Credit.objects.aggregate(Sum("princilal"))["princilal__sum"] or Decimal("0.0")
        
        if total_principal == 0:
            return Decimal("0.0")
        
        total_interest = total_principal * Decimal("0.10")
        net_interest =total_interest * Decimal("0.90")

        total_balance = CustomUser.objects.aggregate(Sum("balance"))["balance__sum"] or Decimal("0.0")
        if total_balance ==0:
            return Decimal("0.0")
        
        user_interest =(self.balance / total_balance) * net_interest
        return user_interest.quantize(Decimal("0.0"))

    # --- Fonctions liées au compte ---
    def send_money(self, recipient, amount):
        amount = Decimal(amount)
        if amount <= 0:
            raise ValueError("le montant de l'envoi doit être poditif")
        if self.balance < amount:
            raise ValueError("Solde insuffisant pour effectuer l'envoi.")
        
        self.balance -= amount 
        self.save()

        Transaction.objects.create(
            user = self,
            transaction_type = "ENVOIE",
            amount = amount,
            balance_after =self.balance
        )

        recipient.balance += amount
        recipient.save()

        Transaction.objects.create(
            user = recipient,
            transaction_type ="DEPOT",
            amount=amount,
            balance_after = recipient.balance
        )
        return {
            "sender_balance": self.balance,
            "recipient_balance": recipient.balance
        }


    def deposit_social(self, amount):
        amount =Decimal(amount)
        if amount <= 0:
            raise ValueError('le montant du socila doit être positif.')
        self.social += amount
        self.save()
        Transaction.objects.create(
            user = self,
            transaction_type ="SOCIALE",
            amount =amount,
            balance_after=self.social
        )
    def deposit(self, amount):
        amount = Decimal(amount)
        if amount <= 0:
            raise ValueError("Le montant du dépôt doit être positif.")
        self.balance += amount
        self.save()

        Transaction.objects.create(
            user=self,
            transaction_type="DEPOT",
            amount=amount,
            balance_after=self.balance
        )
        return self.balance

    def withdraw(self, amount):
        amount = Decimal(amount)
        if amount <= 0:
            raise ValueError("Le montant du retrait doit être positif.")
        if self.balance < amount:
            raise ValueError("Solde insuffisant pour ce retrait.")
        self.balance -= amount
        self.save()

        Transaction.objects.create(
            user=self,
            transaction_type="RETRAIT",
            amount=amount,
            balance_after=self.balance
        )
        return self.balance

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ("DEPOT", "Dépôt"),
        ("RETRAIT", "Retrait"),
        ("SOCIALE","Sociale"),
        ("ENVOIE", "Envoi"),
        ("ANNULATION", "Annulation"),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=50, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            today = datetime.date.today().strftime("%Y%m%d")
            count_today = Transaction.objects.filter(created_at__date=datetime.date.today()).count() + 1
            self.reference = f"{self.transaction_type}-{today}-{count_today:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - {self.user.username} - {self.transaction_type} {self.amount}"
    

    
    def cancel(self):
        """Annule la transaction en créant une opération inverse"""
        if self.transaction_type == "ANNULATION":
          raise ValueError("Impossible d'annuler une transaction déjà annulée.")
        
        with db_transaction.atomic():
            if self.transaction_type =="DEPOT":
                self.user.balance -= self.amount
            elif self.transaction_type in ["RETRAI","ENVOIE"]:
                self.user.balance += self.amount
            elif self.transaction_type =="SOCIALE":
                self.user.social -= self.amount
            else:
                raise ValueError("Type de transaction non reconnu pour annulation.")
            
            self.user.save()

            revese_tx = Transaction.objects.create(
                user=self.user,
                transaction_type ="ANNULATION",
                amount=self.amount,
                balance_after = self.user.balance,
                reference=f"ANNUL-{self.reference}"
            )
            return revese_tx
         

class Credit(models.Model):
    user =models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="credits")
    princilal=models.DecimalField(max_digits=12, decimal_places=2) # montant emprunté
    total_due = models.DecimalField(max_digits=12, decimal_places=2)# montant avec intérêt
    balance_due = models.DecimalField(max_digits=12, decimal_places=2)# montant rest a payer 
    interset_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.10")) #10% 
    created_at = models.DateTimeField(auto_now=True)
    due_date = models.DateField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.total_due:
            self.total_due = self.princilal * (1 + self.interset_rate)
            self.balance_due = self.total_due

        if not self.due_date:
            self.due_date =(self.created_at or timezone.now()).date() + timedelta(days=90)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Crédit {self.princilal} - Total à rembourser: {self.total_due} - {self.user.username}"
    
    def make_repayement(self, amount):
        """Enregistrement un remboursement"""
        amount = Decimal(amount)
        if amount <= 0:
            raise ValueError("Le montant du remboursemnt doit être positif")
        if self.balance_due <= 0:
            raise ValueError("Ce crédit est déjà entièrement remboursé ")
        
        self.balance_due -= amount
        if self.balance_due <= 0:
            self.balance_due = Decimal("0.00")
            self.is_paid = True
        self.save()

# transaction credit 
class CreditTransaction(models.Model):
    TRANSACTION_TYPES = (
        ("CREDIT", "Crédit"),
        ("REMBOURSEMENT", "Remboursement"),
        ("ANNULATION", "Annulation"),
    )       
    credit = models.ForeignKey(Credit, on_delete=models.CASCADE, related_name='transac')
    transaction_type = models.CharField(max_length=15, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=50, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self,*args, **kwargs):
        if not self.reference:
            today = datetime.datetime.today().strftime("%Y%m%d")
            count_today = CreditTransaction.objects.filter(created_at__date = datetime.date.today()).count() + 1
            self.reference =f"{self.transaction_type}-{today}-{count_today:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference}-{self.transaction_type} {self.amount} - {self.credit.user.username}"
    
    def cancel(self):
        """annuler la transaction en créant une opération inverse"""
        if self.transaction_type =="ANNULATION":
            raise ValueError("Imposible d'annuler une transaction déjà annulée.")
        with db_transaction.atomic():
            if self.transaction_type =="CREDIT":
                self.credit.princilal -= self.amount
            elif self.transaction_type =="REMBOURSEMENT":
                self.credit.balance_due +=self.amount
            else:
                raise ValueError("Type de transaction non reconnu pour annulation.")
            
            self.credit.save()

            revese_tx = CreditTransaction.objects.create(
                credit=self.credit,
                transaction_type = "ANNULATION",
                amount = self.amount,
                reference=f"ANNUL-{self.reference}"

            )
            return revese_tx

#class pour le bon de sortie 
class CashOut(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now=True)
    motif = models.CharField(max_length=30, default="Aucun motif")
    
    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def total_amount(self):
        return sum(detail.amount for detail in self.details.all())

class CashOutDetail(models.Model):
    cashout = models.ForeignKey(CashOut, related_name='details', on_delete=models.CASCADE)
    reason = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self): 
        return f"{self.reason} - {self.amount}"
    
# model pour le cycle
class Cycle(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.start_date} → {self.end_date})"
    def contains(self, date=None):
        """Vérifie si une date donnée est dans le cycle"""
        if date is None:
            date = timezone.now().date()
        return self.start_date <= date <=self.end_date
    
    @classmethod
    def current_cycle(cls):
        """Retourne le cycle actif qui contient la date du jour"""
        today = timezone.now().date()
        return cls.objects.filter(start_date__lte=today, end_date__gte=today, is_activa= True).first()

class PasswordResetCode(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        # valable 15 minutes
        return not self.is_used and self.created_at >= timezone.now() - timedelta(minutes=15)


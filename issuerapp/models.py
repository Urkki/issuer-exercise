from django.db import models

TRANSFER_TYPES = {
    ("credit", "credit"),
    ("debit",  "debit")
}
TRANSACTION_TYPES = {
    ("authorization", "authorization"),
    ("presentment", "presentment"),
    ("settlement", "settlement")
}

#Accounts (holds monetary value in some currency)
class Accounts(models.Model):
    cardholder = models.CharField(max_length=50, primary_key=True)

#Transfers (representing a debit or credit)
class Transfers(models.Model):
    transfer_type = models.CharField(choices=TRANSFER_TYPES, max_length=6)
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(decimal_places=2, max_digits=99)
    account = models.ForeignKey(Accounts, on_delete=models.PROTECT)

#Transactions (bundles a number of transfers to represent movement of value between accounts)
class Transactions(models.Model):
    transfer_from = models.ForeignKey(Transfers, on_delete=models.PROTECT, related_name="transfer_from")
    transfer_to = models.ForeignKey(Transfers, on_delete=models.PROTECT, related_name="transfer_to")
    transaction_type = models.CharField(choices=TRANSACTION_TYPES, max_length=13)
    created = models.DateTimeField("time when transaction is created.")

#python manage.py makemigrations issuerapp

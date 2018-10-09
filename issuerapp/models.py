from django.db import models
from django.utils import timezone

TRANSFER_TYPES = {
    ("credit", "credit"),
    ("debit",  "debit")
}
TRANSACTION_TYPES = {
    ("authorization", "authorization"),
    ("presentment", "presentment"),
    ("settlement", "settlement")
}

ISSUER_NAME = "issuer"

#Accounts (holds monetary value in some currency)
class Accounts(models.Model):
    cardholder = models.CharField(max_length=50, primary_key=True)


    ''' Gets existing account if it exists. Otherwise a new account is created. '''
    @staticmethod
    def get_account(cardholder_name):
        if Accounts.objects.filter(pk=cardholder_name).exists():
            account = Accounts.objects.get(pk=cardholder_name)
            return account
        else:
            # create a new account and save it.
            new_account = Accounts(cardholder=cardholder_name)
            new_account.save()
            return new_account

#Transfers (representing a debit or credit)
class Transfers(models.Model):
    transfer_type = models.CharField(choices=sorted(TRANSFER_TYPES), max_length=6)
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(decimal_places=2, max_digits=99)
    account = models.ForeignKey(Accounts, on_delete=models.PROTECT)

#Transactions (bundles a number of transfers to represent movement of value between accounts)
class Transactions(models.Model):
    transfer_from = models.ForeignKey(Transfers, on_delete=models.CASCADE, related_name="transfer_from")
    transfer_to = models.ForeignKey(Transfers, on_delete=models.CASCADE, related_name="transfer_to")
    transaction_type = models.CharField(choices=sorted(TRANSACTION_TYPES), max_length=13)
    created = models.DateTimeField("time when transaction was created.")

    @staticmethod
    def create_transaction(debit_account, credit_account, transaction_type, currency, amount):
        debit_transfer = Transfers(transfer_type="debit", currency=currency, amount=amount, account=debit_account)
        credit_transfer = Transfers(transfer_type="credit", currency=currency, amount=amount, account=credit_account)
        created = timezone.now()

        try:
            debit_transfer.save()
            credit_transfer.save()
            #create transaction here because transfers had to be saved before we can reference them.
            transaction = Transactions(transfer_from=debit_transfer, transfer_to=credit_transfer,
                                       transaction_type=transaction_type, created=created)
            transaction.save()
        except Exception as e:
            #if this fails. delete objects.
            if not debit_transfer.id is None:
                debit_transfer.delete()
            if not credit_transfer.id is None:
                credit_transfer.delete()
            if not transaction.id is None:
                transaction.delete()
            raise e

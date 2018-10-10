from django.db import models
from django.utils import timezone
from django.db.models import Q
from json import dumps

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
    main_currency = models.CharField(max_length=3)

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

    def __str__(self):
        return  "{}".format(self.cardholder)

#Transfers (representing a debit or credit)
class Transfers(models.Model):
    transfer_type = models.CharField(choices=sorted(TRANSFER_TYPES), max_length=6)
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(decimal_places=2, max_digits=99)
    account = models.ForeignKey(Accounts, on_delete=models.PROTECT)

    def __str__(self):
        return "{} {} {} {}".format(self.transfer_type, self.amount,  self.currency, self.account)

#Transactions (bundles a number of transfers to represent movement of value between accounts)
class Transactions(models.Model):
    transfer_from = models.ForeignKey(Transfers, on_delete=models.CASCADE, related_name="transfer_from")
    transfer_to = models.ForeignKey(Transfers, on_delete=models.CASCADE, related_name="transfer_to")
    transaction_type = models.CharField(choices=sorted(TRANSACTION_TYPES), max_length=13)
    created = models.DateTimeField("time when transaction was created.",default=timezone.now)

    @staticmethod
    def create_transaction(debit_account, credit_account, transaction_type, currency, amount):
        debit_transfer = Transfers(transfer_type="debit", currency=currency, amount=amount, account=debit_account)
        credit_transfer = Transfers(transfer_type="credit", currency=currency, amount=amount, account=credit_account)

        try:
            debit_transfer.save()
            credit_transfer.save()
            #create transaction here because transfers had to be saved before we can reference them.
            transaction = Transactions(transfer_from=debit_transfer, transfer_to=credit_transfer,
                                       transaction_type=transaction_type)
            transaction.save()
            return transaction
        except Exception as e:
            #if this fails. delete objects.
            if not debit_transfer.id is None:
                debit_transfer.delete()
            if not credit_transfer.id is None:
                credit_transfer.delete()
            if not transaction.id is None:
                transaction.delete()
            raise e

    def __str__(self):
        return "{0} {1} from: {2} to: {3}"\
            .format(self.created, self.transaction_type, self.transfer_from, self.transfer_to)

    @staticmethod
    def show_balances(account_name, time_threshold=timezone.now()):
        """
        Calculates ledger balance and available balance for given account.
        :param account_name: The name of account to get balance
        :param time_threshold: Time threshold. Balance before this is given.
        :return: ledger balance and available balance as in JSON format. 
        """
        ledger_balance = Transactions.get_ledger_balance(account_name, time_threshold)

    @staticmethod
    def get_ledger_balance(account_name, time_threshold=timezone.now()):
        """
        Calculates ledger balance for given account.
        :param account_name: The name of account to get ledger balance
        :param time_threshold: Time threshold. 
        :return: ledger balance in JSON format. 
        """

        acc = Accounts.get_account(account_name)
        transactions_from = Transactions.objects.filter(Q(created__lte=time_threshold),
                                                        Q(transfer_from__account__exact=acc),
                                                        Q(transaction_type__exact="presentment"),
                                                        Q(transfer_from__currency__iexact=acc.main_currency))
        transactions_to = Transactions.objects.filter(Q(created__lte=time_threshold),
                                                      Q(transfer_to__account__exact=acc),
                                                      Q(transaction_type__exact="presentment"),
                                                      Q(transfer_from__currency__iexact=acc.main_currency))
        debit_amount = 0
        credit_amount = 0
        # debit transfer
        for transaction in transactions_from:
            debit_amount += transaction.transfer_from.amount
        # credit transfer
        for transaction in transactions_to:
            credit_amount += transaction.transfer_to.amount

        ledger_balance = credit_amount - debit_amount
        balance_json = {
            "ledger_balance": str(ledger_balance)
        }
        #print("Ledger debit: {} credit: {} balance: {}".format(debit_amount, credit_amount, ledger_balance))
        return dumps(balance_json)




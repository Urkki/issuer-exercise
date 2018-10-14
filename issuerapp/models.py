from django.db import models
from django.utils import timezone
from django.db.models import Q
from django.core.validators import MinValueValidator
from moneyed import CURRENCIES_BY_ISO
from decimal import Decimal

#create currency tuples for validating database fields.
CURRENCIES = [ (value.code, value.code) for value in CURRENCIES_BY_ISO.values()]

TRANSFER_TYPES = (
    ("credit", "credit"),
    ("debit",  "debit")
)
TRANSACTION_TYPES = (
    ("authorization", "authorization"),
    ("presentment", "presentment"),
    ("settlement", "settlement")
)

ISSUER_NAME = "issuer"

class Accounts(models.Model):
    """
    Represents an account of cardholder with assumption that cardholder can have one account. 
    Cardholder field can be considered as card_id. 
    """
    cardholder = models.CharField(max_length=50, primary_key=True)
    main_currency = models.CharField(choices=CURRENCIES, max_length=3, default="EUR")

    @staticmethod
    def get_account(cardholder_name, can_create_new_account=False):
        """
        Gets an account.
        :param cardholder_name: The name of the account owner.
        :param can_create_new_account: If existing account is not found, the can_create_new_account boolean parameter 
        determines if a new account can be created. The default currency is applied.
        :return: Returns created or existing account.
        """
        if Accounts.objects.filter(pk=cardholder_name).exists():
            account = Accounts.objects.get(pk=cardholder_name)
            return account
        elif can_create_new_account:
            # create a new account and save it.
            new_account = Accounts(cardholder=cardholder_name)
            new_account.save()
            return new_account
        else:
            raise Accounts.DoesNotExist("The account \"{}\" does not exist.".format(cardholder_name))

    def save(self, *args, **kwargs):
        self.full_clean()
        return super(Accounts, self).save(*args, **kwargs)

    def __str__(self):
        return  "{}".format(self.cardholder)

class Transfers(models.Model):
    """
    Transfers model represents a debit or credit transfer.
        Fields:
        - transfer_type: credit or debit
        - currency: ISO standard char sequence.
        - amount: Transfer amount.
        - account: A reference to related account where transfer was performed.
    """
    transfer_type = models.CharField(choices=TRANSFER_TYPES, blank=False, max_length=6)
    currency = models.CharField(choices=CURRENCIES, max_length=3, blank=False)
    amount = models.DecimalField(decimal_places=2, max_digits=14, blank=False,
                                 validators=[MinValueValidator(Decimal('0.01'))]) # could use django-money
    account = models.ForeignKey(Accounts, on_delete=models.PROTECT, blank=False)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super(Transfers, self).save(*args, **kwargs)

    def __str__(self):
        return "{} {} {} {}".format(self.transfer_type, self.amount,  self.currency, self.account)

class Transactions(models.Model):
    """
    Transactions model groups debit and credit transfers between accounts.  
        Fields:
        - transaction_id: It is used to identify authorization and presentment transactions.
        - transfer_from: A debit Transfer. The funds are deducted from this account.
        - transfer_to: A credit Transfer. The funds are added to this account.
        - transaction_type: The type of transaction. Possible values: authorization, presentment and settlement.
        - created: A timestamp when transaction was created. 
    """
    transaction_id = models.CharField(max_length=20, blank=True)
    transfer_from = models.ForeignKey(Transfers, on_delete=models.CASCADE, related_name="transfer_from", blank=False)
    transfer_to = models.ForeignKey(Transfers, on_delete=models.CASCADE, related_name="transfer_to", blank=False)
    transaction_type = models.CharField(choices=TRANSACTION_TYPES, max_length=13, blank=False)
    created = models.DateTimeField("time when transaction was created.",default=timezone.now, blank=False)

    @staticmethod
    def create_transaction(debit_account, credit_account, transaction_type, currency, amount, transaction_id=""):
        """
        Creates a transaction and saves it into database.
        :param debit_account: The account model where the money is taken.
        :param credit_account: The account where the money is given.
        :param transaction_type: The type of transaction. Possible values are "authorization", "presentment" or 
        "settlement"
        :param currency: Currency in ISO character format. 
        :param amount: Transaction amount. The minimum amount is 0.01
        :param transaction_id: Optional parameter for identifying transactions.
        :return: Returns the created transaction.
        """
        debit_transfer = Transfers(transfer_type="debit", currency=currency, amount=str(amount), account=debit_account)
        credit_transfer = Transfers(transfer_type="credit", currency=currency, amount=str(amount), account=credit_account)

        debit_transfer.save()
        try:
            credit_transfer.save()
        except Exception as e:
            debit_transfer.delete()
            raise e

        # create transaction here because transfers had to be saved before we can reference them.
        transaction = Transactions(transfer_from=debit_transfer, transfer_to=credit_transfer,
                                   transaction_type=transaction_type, transaction_id=transaction_id)
        try:
            transaction.save()
            return transaction
        except Exception as e:
            #if transaction saving fails, delete created transfers
            credit_transfer.save()
            debit_transfer.delete()
            raise e

    def save(self, *args, **kwargs):
        self.full_clean()
        return super(Transactions, self).save(*args, **kwargs)

    def __str__(self):
        return "{0} {1} from: {2} to: {3} t_id: {4}"\
            .format(self.created, self.transaction_type, self.transfer_from, self.transfer_to, self.transaction_id)

    @staticmethod
    def get_transactions(account_name, start_datetime, end_datetime):
        """
        Gets present transactions of account for given timeframe. 
        :param account_name: The account name which has to be in transaction. 
        :param start_datetime: The start time of timeframe.
        :param end_datetime: The end time of timeframe.
        :return: Returns presented transactions between start time and end time.
        """
        acc = Accounts.get_account(account_name)

        if isinstance(start_datetime, timezone.datetime) and isinstance(end_datetime, timezone.datetime):
            if start_datetime > end_datetime:
                raise ValueError("Start datetime is greater than end datetime. Query can't find any results,")

        transactions = Transactions.objects.filter(Q(created__gte=start_datetime), Q(created__lte=end_datetime),
                                                   Q(transfer_to__account__exact=acc) |
                                                   Q(transfer_from__account__exact=acc),
                                                   Q(transaction_type__exact="presentment"))
        return transactions

    @staticmethod
    def show_balances(account_name, time_threshold=timezone.now()):
        """
        Calculates ledger balance and available balance for given account.
        :param account_name: The name of account to get balance
        :param time_threshold: Time threshold. Balance before or equal this time threshold is given.
        :return: ledger balance and available balance in dictionary format. 
        """
        ledger_balance = Transactions.get_ledger_balance(account_name, time_threshold)
        available_balance = Transactions.get_available_balance(account_name)
        #merge dictionaries
        balances = {**ledger_balance, **available_balance}
        return balances

    @staticmethod
    def get_ledger_balance(account_name, time_threshold=timezone.now()):
        """
        Calculates ledger balance for given account.
        :param account_name: The name of account to get ledger balance
        :param time_threshold: Time threshold. 
        :return: ledger balance as in dictionary format. 
        """

        acc = Accounts.get_account(account_name)
        transactions_from = Transactions.objects.filter(Q(created__lte=time_threshold),
                                                        Q(transfer_from__account__exact=acc),
                                                        Q(transaction_type__exact="presentment"),
                                                        Q(transfer_from__currency__iexact=acc.main_currency))
        transactions_to = Transactions.objects.filter(Q(created__lte=time_threshold),
                                                      Q(transfer_to__account__exact=acc),
                                                      Q(transaction_type__exact="presentment"),
                                                      Q(transfer_to__currency__iexact=acc.main_currency))
        ledger_balance = Transactions.calculate_balance(transactions_from, transactions_to)
        balance = {
            "ledger_balance": str(ledger_balance)
        }
        return balance

    @staticmethod
    def calculate_balance(transactions_from, transactions_to):
        """
        Calculates balance between debit and credit transactions.
        :param transactions_from: Debit transactions of selected account. 
        :param transactions_to: Credit transactions of selected account.
        :return: Balance
        """
        debit_amount = 0
        credit_amount = 0
        # debit transfer
        for transaction in transactions_from:
            debit_amount += transaction.transfer_from.amount
        # credit transfer
        for transaction in transactions_to:
            credit_amount += transaction.transfer_to.amount

        balance = credit_amount - debit_amount
        return balance

    @staticmethod
    def get_available_balance(account_name):
        """
        Calculates available balance for given account.
        :param account_name: The account name.
        :return: Returns a dictionary with "available_balance" key.
        """
        acc = Accounts.get_account(account_name)
        transactions_from = Transactions.objects.filter(Q(transfer_from__account__exact=acc),
                                                        Q(transaction_type__exact="presentment") |
                                                        Q(transaction_type__exact="authorization"),
                                                        Q(transfer_from__currency__iexact=acc.main_currency))
        transactions_to = Transactions.objects.filter(Q(transfer_to__account__exact=acc),
                                                      Q(transaction_type__exact="presentment") |
                                                      Q(transaction_type__exact="authorization"),
                                                      Q(transfer_to__currency__iexact=acc.main_currency))
        available_balance = Transactions.calculate_balance(transactions_from, transactions_to)
        balance = {
            "available_balance": str(available_balance)
        }
        return balance
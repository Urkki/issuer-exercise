from django.test import TestCase
from .models import Transactions, Accounts, Transfers
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from pytz import UTC

class AccountsTests(TestCase):
    SCHEME = "scheme"

    def test_get_existing_account_successfully(self):
        Accounts.objects.create(cardholder=self.SCHEME, main_currency="EUR")
        Accounts.get_account(self.SCHEME, can_create_new_account=False)

    def test_get_account_not_found(self):
        with self.assertRaises(Accounts.DoesNotExist):
            Accounts.get_account(self.SCHEME)

    def test_get_account_create_new_account(self):
        account = Accounts.get_account(self.SCHEME, can_create_new_account=True)
        self.assertEqual(account.cardholder, self.SCHEME)
        self.assertEqual(account.main_currency, "EUR")

class TransactionsTests(TestCase):
    MILLIONAIRE = "millionaire"
    STUDENT = "student"
    ISSUER = "issuer"

    def __create_test_transaction(self, debit_cardholder, credit_cardholder,
                                  transaction_type="authorization", currency="EUR", amount=100):
        debit_account = Accounts.objects.get(cardholder=debit_cardholder)
        credit_account = Accounts.objects.get(cardholder=credit_cardholder)
        transaction = Transactions.create_transaction(debit_account, credit_account,
                                                      transaction_type, currency, amount)
        return transaction

    def __create_test_transactions(self):
        # student debit 100 EUR, issuer credit 100 EUR auth
        transaction = self.__create_test_transaction(self.STUDENT, self.ISSUER)
        transaction.created = self.test_datetime
        transaction.save()
        # millionaire debit 100 EUR, issuer credit 100 EUR auth
        transaction = self.__create_test_transaction(self.MILLIONAIRE, self.ISSUER)
        transaction.created = self.test_datetime
        transaction.save()
        # student debit 100 EUR, millionaire credit 100 EUR auth
        transaction = self.__create_test_transaction(self.STUDENT, self.MILLIONAIRE)
        transaction.created = self.test_datetime
        transaction.save()
        # issuer debit 100000 EUR, millionaire credit 100000 EUR presentment
        transaction = self.__create_test_transaction(self.ISSUER, self.MILLIONAIRE,
                                                     transaction_type="presentment", amount=100000)
        transaction.created = self.test_datetime
        transaction.save()

    def setUp(self):
        Accounts.objects.create(cardholder=self.ISSUER, main_currency="EUR")
        Accounts.objects.create(cardholder=self.STUDENT, main_currency="EUR")
        Accounts.objects.create(cardholder=self.MILLIONAIRE, main_currency="EUR")
        self.test_datetime = timezone.datetime(2018, 10, 10, 10, 10, 10, 10, tzinfo=UTC)

    def test_create_transaction_is_successful(self):
        """
         Tests if creating a transaction is successful.
         """

        debit_account = Accounts.objects.get(cardholder=self.ISSUER)
        credit_account = Accounts.objects.get(cardholder=self.MILLIONAIRE)
        transaction = Transactions.create_transaction(debit_account, credit_account, transaction_type="authorization",
                                                      currency="EUR", amount=0.01)
        self.assertIs(type(transaction), Transactions) # right type is returned
        self.assertIn(transaction, Transactions.objects.all()) # transaction is saved
        self.assertEqual(transaction.transaction_type, "authorization")  # correct transaction_type

        self.assertIs(transaction.transfer_from.account, debit_account) # transfer object has a right account
        self.assertEqual(transaction.transfer_from.amount, Decimal('0.01'))  # transfer object has a right amount
        self.assertEqual(transaction.transfer_from.currency, "EUR")  # transfer object has a right currency
        self.assertEqual(transaction.transfer_from.transfer_type, "debit") # transfer object has a right transfer type

        self.assertIs(transaction.transfer_to.account, credit_account)
        self.assertEqual(transaction.transfer_to.amount, Decimal('0.01'))
        self.assertEqual(transaction.transfer_to.currency, "EUR")
        self.assertEqual(transaction.transfer_to.transfer_type, "credit")

    def test_create_transaction_invalid_parameters(self):
        """
         Tests create_transaction function with invalid parameters.
         """
        credit_account = Accounts.objects.get(cardholder=self.ISSUER)

        with self.assertRaises(ValueError):
            Transactions.create_transaction("wrong_parameter", credit_account, transaction_type="authorization",
                                            currency="EUR", amount=100)
        with self.assertRaises(ValueError):
            Transactions.create_transaction(credit_account, "wrong_parameter", transaction_type="authorization",
                                            currency="EUR", amount=100)
        with self.assertRaises(ValidationError):
            Transactions.create_transaction(credit_account, credit_account, transaction_type="not_valid_choice",
                                            currency="EUR", amount=100)
        with self.assertRaises(ValidationError):
            Transactions.create_transaction(credit_account, credit_account, transaction_type="authorization",
                                            currency=10, amount=100)
        with self.assertRaises(ValidationError):
            Transactions.create_transaction(credit_account, credit_account, transaction_type="authorization",
                                            currency="EUR", amount=0.00)

    def test_ledger_balance_is_successful(self):
        """
        Tests if getting ledger balance is successful.
        """
        self.__create_test_transactions()

        balance_dict = Transactions.get_ledger_balance(self.ISSUER, time_threshold=self.test_datetime)
        self.assertEqual(balance_dict["ledger_balance"], "-100000.00")

        balance_dict = Transactions.get_ledger_balance(self.STUDENT, time_threshold=self.test_datetime)
        self.assertEqual(balance_dict["ledger_balance"], "0")

        balance_dict = Transactions.get_ledger_balance(self.MILLIONAIRE, time_threshold=self.test_datetime)
        self.assertEqual(balance_dict["ledger_balance"], "100000.00")

    def test_ledger_balance_invalid_parameters(self):
        """
         Tests get_ledger_balance with invalid parameters.
        """
        self.__create_test_transactions()

        with self.assertRaises(Accounts.DoesNotExist):
            Transactions.get_ledger_balance("abrakadabra", time_threshold=self.test_datetime)

        with self.assertRaises(ValidationError):
            Transactions.get_ledger_balance(self.ISSUER, time_threshold="time")

    def test_get_available_balance_successful(self):
        """
        Tests if getting available balance is successful.
        """
        self.__create_test_transactions()

        balance = Transactions.get_available_balance(self.ISSUER)
        self.assertEqual(balance["available_balance"], "-99800.00")
        balance = Transactions.get_available_balance(self.STUDENT)
        self.assertEqual(balance["available_balance"], "-200.00")
        balance = Transactions.get_available_balance(self.MILLIONAIRE)
        self.assertEqual(balance["available_balance"], "100000.00")

    def test_get_available_balance_invalid_parameter(self):
        """
        Tests that unknown account name throws an exception.
        """
        self.__create_test_transactions()
        with self.assertRaises(Accounts.DoesNotExist):
            Transactions.get_available_balance("wrong")

    def test_show_balance_successful(self):
        self.__create_test_transactions()
        balances = Transactions.show_balances(self.ISSUER)
        self.assertEqual(balances["available_balance"], "-99800.00")
        self.assertEqual(balances["ledger_balance"], "-100000.00")

    def test_show_balance_invalid_account(self):
        self.__create_test_transactions()
        with self.assertRaises(Accounts.DoesNotExist):
            Transactions.show_balances("invalid")

    def test_get_transactions_successfully(self):
        self.__create_test_transactions()
        ten_seconds = timezone.timedelta(seconds=10)
        start_time = self.test_datetime - ten_seconds
        end_time =  self.test_datetime + ten_seconds
        transactions = Transactions.get_transactions(self.ISSUER, start_time, end_time)
        self.assertEqual(transactions.count(), 1)

        #create more transactions. There should be 5 valid transactions now but 3 in given timeframe.
        times = [start_time, end_time, start_time - ten_seconds, end_time + ten_seconds ]
        for time in times:
            transaction = self.__create_test_transaction(self.MILLIONAIRE, self.ISSUER,
                                                         transaction_type="presentment", amount=100000)
            transaction.created = time
            transaction.save()

        transactions = Transactions.get_transactions(self.ISSUER, start_time, end_time)
        self.assertEqual(transactions.count(), 3)

    def test_get_transactions_invalid_parameters(self):
        self.__create_test_transactions()
        ten_seconds = timezone.timedelta(seconds=10)
        with self.assertRaises(ValidationError):
            Transactions.get_transactions(self.ISSUER, "should_be_time", self.test_datetime)
        with self.assertRaises(ValidationError):
            Transactions.get_transactions(self.ISSUER, self.test_datetime, "should_be_time")
        with self.assertRaises(Accounts.DoesNotExist):
            Transactions.get_transactions("unknown", self.test_datetime, self.test_datetime)
        #end time is less than start time
        with self.assertRaises(ValueError):
            Transactions.get_transactions(self.ISSUER, self.test_datetime, self.test_datetime - ten_seconds)

class AuthorizationWebhookTests(TestCase):

    STUDENT = "student"
    ISSUER = "issuer"

    AUTH_DATA_OK = {
        "type": "authorization",
        "card_id": STUDENT,
        "transaction_id": "1234ZORRO",
        "merchant_name": "SNEAKERS R US",
        "merchant_country": "US",
        "merchant_mcc": "5139",
        "billing_amount": "90.00",
        "billing_currency": "EUR",
        "transaction_amount": "100.00",
        "transaction_currency": "USD"
    }

    AUTH_DATA_NOK = {
        "type": "authorization",
        "card_id": STUDENT,
        "transaction_id": "1234ZORRO",
        "merchant_name": "SNEAKERS R US",
        "merchant_country": "US",
        "merchant_mcc": "5139",
        "billing_amount": "90000.00",
        "billing_currency": "EUR",
        "transaction_amount": "100000.00",
        "transaction_currency": "USD"
    }

    def setUp(self):
        Accounts.objects.create(cardholder=self.ISSUER, main_currency="EUR")
        Accounts.objects.create(cardholder=self.STUDENT, main_currency="EUR")
        issuer_account = Accounts.objects.get(cardholder=self.ISSUER)
        student_account = Accounts.objects.get(cardholder=self.STUDENT)
        Transactions.create_transaction(issuer_account, student_account,
                                                      transaction_type="presentment", currency="EUR", amount=1111.11)
        Transactions.create_transaction(issuer_account, student_account,
                                                      transaction_type="presentment", currency="EUR", amount=21.96)
        Transactions.create_transaction(student_account, issuer_account,
                                                      transaction_type="authorization", currency="EUR", amount=51.55)
        #the student should have 1111.11 + 21.96 - 51.55 = 1081.52 EUR

    def test_authorization_webhook_successful(self):
        response = self.client.get("/api/authorization", self.AUTH_DATA_OK)
        self.assertIn(r"991.52", str(response.content))
        self.assertEqual(response.status_code, 200)

    def test_authorization_webhook_not_enough_funds(self):
        response = self.client.get("/api/authorization", self.AUTH_DATA_NOK)
        self.assertEqual(response.status_code, 403)

    def test_authorization_webhook_invalid_request(self):
        response = self.client.get("/api/authorization")
        self.assertEqual(response.status_code, 400)
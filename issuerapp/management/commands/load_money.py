from django.core.management.base import BaseCommand
from issuerapp.models import Accounts, Transactions, ISSUER_NAME

class Command(BaseCommand):
    help = 'Load money into cardholder\'s account. Creates new account if needed.'

    def add_arguments(self, parser):
        parser.add_argument('cardholder', type=str)
        parser.add_argument('amount', type=float)
        parser.add_argument('currency', type=str)

    def handle(self, *args, **options):
        cardholder = options['cardholder']
        amount = options['amount']
        currency = options['currency']
        #TODO: should check arguments here
        
        issuer_account = Accounts.get_account(ISSUER_NAME, can_create_new_account=True)
        cardholder_account = Accounts.get_account(cardholder, can_create_new_account=True)

        try:
            Transactions.create_transaction(debit_account=issuer_account, credit_account=cardholder_account,
                                        transaction_type="authorization", currency=currency, amount=amount)
            self.stdout.write(self.style.SUCCESS("Successfully transferred {0} {1} to {2}."
                                                 .format(amount, currency, cardholder_account.cardholder)))
        except Exception as e:
            self.stdout.write(self.style.ERROR("Transfer FAILED! Error: {0}".format(e)))
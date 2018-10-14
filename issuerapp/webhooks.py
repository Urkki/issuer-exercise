from django.http import HttpResponse
from .models import Transactions, Accounts, ISSUER_NAME, SCHEME_NAME
from decimal import Decimal

def authorization(request):
    """
    Handles a authorization request.
    :param request: WSGIRequest which contains request data.
    :return: HttpResponse
    """
    try:
        cardholder = request.GET["card_id"]  # use GET request for demo purposes.
        balances = Transactions.get_available_balance(cardholder)
        balance_amount = Decimal(balances["available_balance"])
        billing_amount = Decimal(request.GET["billing_amount"])
        currency = request.GET["billing_currency"]
        if balance_amount >= billing_amount:  # authorization is possible
            balance_amount_after = balance_amount - billing_amount
            #reserve amount.
            cardholder_account = Accounts.get_account(cardholder)
            issuer_account =  Accounts.get_account(ISSUER_NAME)
            Transactions.create_transaction(cardholder_account, issuer_account, "authorization", currency,
                                            billing_amount, transaction_id=request.GET["transaction_id"])
            return HttpResponse('balance after transaction: {}'.format(balance_amount_after), status=200)  # OK
        else:
            return HttpResponse('The payment is declined.', status=403)  # Forbidden
    except:
        return HttpResponse('Unknown error', status=400) # Bad Request

def presentment(request):
    try:
        transaction = Transactions.objects.get(transaction_id=request.GET["transaction_id"])
        transaction.transaction_type = "presentment"
        transaction.save()
        #create debt to the scheme
        issuer_account = Accounts.get_account(ISSUER_NAME)
        scheme_account = Accounts.get_account(SCHEME_NAME)
        currency = request.GET["settlement_currency"]
        amount = request.GET["settlement_amount"]
        Transactions.create_transaction(issuer_account, scheme_account, "settlement", currency, amount)
        return HttpResponse('Presentment successful', status=200)  # OK
    except:
        return HttpResponse('Unknown error', status=400) # Bad Request
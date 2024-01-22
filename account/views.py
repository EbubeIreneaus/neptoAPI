import json

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Q
from django.forms import model_to_dict
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from transaction.views import updateTransactions, generate_transact_key
from transaction.models import Transaction
from authentication.models import Profile
from manager.models import Setup
from .serializers import AccountSerial, CryptoSerial
from.models import Account
from django.http import JsonResponse
from authentication.serializers import ProfileSerial
# Create your views here.

def accountDetails(request, profileId):
    try:
        updateTransactions(profileId)
    except:
        pass
    try:
        account = Account.objects.get(profile__id = profileId)
        serialized_account = AccountSerial(account)
        return JsonResponse(serialized_account.data, safe=False)
    except Account.DoesNotExist:
        return JsonResponse({'status':'failed', 'code':'account_not_found'})
    except Exception as e:
        return JsonResponse({'status': 'failed', 'code': str(e)})

@csrf_exempt
def change_user_data(request):
    data = json.loads(request.body)
    profileId = request.headers.get('profile-id','')
    if data['first_name'] != '' or data['last_name'] != '':
        try:
            profile = Profile.objects.get(id=profileId)
            user = User.objects.get(id=profile.user.id)
            user.first_name = data['first_name']
            user.last_name = data['last_name']
            user.save()
            return JsonResponse({'status':'success'})
        except Exception:
            pass
    return JsonResponse({'status':'failed'})


@csrf_exempt
def change_profile_data(request):
    data = json.loads(request.body)
    profileId = request.headers.get('profile-id','')
    if data['phone'] != '' or data['country'] != '':
        try:
            profile = Profile.objects.get(id=profileId)
            profile.country = data['country']
            profile.country_code = data['code']
            profile.phone = data['phone']
            profile.save()
            return JsonResponse({'status':'success'})
        except Exception:
            pass
    return JsonResponse({'status':'failed'})

@csrf_exempt
def change_security_data(request):
    data = json.loads(request.body)
    profileId = request.headers.get('profile-id','')
    if data['new'] != '' or data['old'] != '':
        try:
            profile = Profile.objects.get(id=profileId)
            user = authenticate(username=profile.user.username, password=data['old'])
            if user is not None:
                user.set_password(data['new'])
                user.save()
                return JsonResponse({'status':'success'})
        except Exception:
            pass
    return JsonResponse({'status':'failed'})

def get_referrals(request):
    profileId = request.GET.get('profile-id', '')

    try:
        profiles = Profile.objects.filter(referred_by__id=profileId)
        serialProfiles = ProfileSerial(profiles, many=True)
        return JsonResponse(serialProfiles.data, safe=False)
    except Exception as e:
        return JsonResponse({'status':'failed', 'code':str(e)})

def transfer(request):
    profileId = request.headers.get('profile-id', '')
    amount = int(request.GET.get('amount', ''))
    total_debit = amount + (0.2 * amount)
    user = request.GET.get('user', '')
    try:
        profile = Profile.objects.get(id=profileId)
        user = User.objects.get(Q(username=user) | Q(email=user))
        receiver_profile = Profile.objects.get(user__id = user.id)
        sender_acct = Account.objects.get(profile__id = profileId)
        receiver_acct = Account.objects.get(profile__id = receiver_profile.id)
        if float(sender_acct.balance) < float(amount):
            return JsonResponse({'status': 'failed', 'code': 'Insufficient Account Balance!'})
        sender_acct.balance = float(sender_acct.balance) - float(total_debit)
        receiver_acct.balance = float(receiver_acct.balance) + float(amount)
        try:
            sender_ts = Transaction.objects.create(transact_id=generate_transact_key(30), profile=profile, type='withdraw',
                                                   status='approved',progress="completed", amount=total_debit)
            receiver_ts = Transaction.objects.create(transact_id=generate_transact_key(30), profile=receiver_profile,
                                                     type='received', status='approved',progress="completed", amount=amount)
        except:
            pass
        sender_acct.save()
        receiver_acct.save()

        return JsonResponse({'status': 'success', 'code': 'transfer successfull'})
    except User.DoesNotExist:
        return JsonResponse({'status': 'failed', 'code': 'No account found on our database!'})
    except User.MultipleObjectsReturned:
        return JsonResponse({'status': 'failed', 'code': 'More than one user found try sending with username!!'})
    except Exception as e:
        return JsonResponse({'status': 'failed', 'code': 'unknown Error occured!', 'msg':str(e)})

@csrf_exempt
def swap(request):
    data = json.loads(request.body)
    source = data['source']
    destination = data['destination']
    no = data['amount']
    profileId = request.headers.get('profile-id', '')
    try:
        account = Account.objects.get(profile__id=profileId)
        act_model = model_to_dict(account)
        if source == 'usd':
            if float(act_model['balance']) < float(no):
                return JsonResponse({'status': 'failed', 'msg': 'Insufficient Funds'})
        else:
            if float(act_model[source]) < float(no):
                return JsonResponse({'status': 'failed', 'msg': 'Insufficient Funds'})
        setups = Setup.objects.get(pk=1)
        setups = model_to_dict(setups)
        source_unit_price = float(setups[source])
        destination_unit_price = float(setups[destination])
        source_price = float(source_unit_price) * float(no)
        value = source_price/destination_unit_price
        if destination == 'usd':
            setattr(account, 'balance', value)
        else:
            setattr(account, destination, value)
        if source == 'usd':
            setattr(account, 'balance', float(act_model['balance'])-float(no))
        else:
            setattr(account, source, float(act_model[source])-float(no))

        account.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status':'failed', 'code':str(e)})

def getCrypto(request):
    profileId = request.headers.get('profile-id')
    try:
        account = Account.objects.get(profile__id=profileId)
        crypt = CryptoSerial(account, many=False)
        return JsonResponse(crypt.data, safe=False)
    except Exception as e:
        return JsonResponse({'status':'failed', 'code':str(e)})

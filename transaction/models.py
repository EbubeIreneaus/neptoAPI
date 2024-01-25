from django.db import models

# Create your models here.
from django.db import models
from authentication.models import Profile
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.forms.models import model_to_dict
from account.models import Account
import time
from django.db import transaction
from manager.models import Setup
import datetime
# Create your models here.
class Transaction(models.Model):
    plans = [
        ('standard','Standard'),
        ('silver', 'Silver'),
        ('premium', 'Premium'),
        ('ultra', 'Ultra'),
        ('promo', 'Promo'),
        ('visa', 'Visa'),
    ]
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    transact_id = models.CharField(max_length=50, unique=True)
    plan = models.CharField(max_length=12, choices=plans, null=True, blank=True)
    channel = models.CharField(max_length=40, default='BTC', null=True, blank=True)
    type = models.CharField(max_length=9, choices=[('deposit','deposit'),("invest", 'invest'),('withdraw', 'withdraw'),
                                                   ('referral','referral'), ("bonus","bonus"), ("received","received")], default='deposit')
    amount = models.DecimalField(decimal_places=2, max_digits=10)
    address = models.CharField(max_length=150, null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=[('pending','pending'), ('approved','approve'),
                                                      ('declined', 'decline')], default="pending")
    progress = models.CharField(max_length=12, choices=[('pending','pending'),('active','active'),
                                                        ('completed', 'completed')], default='pending', editable=False)
    date = models.DateTimeField(auto_now_add=True, null=True, blank=True, editable=True)

    def __str__(self):
        return self.profile.user.first_name +" "+self.profile.user.last_name+" "+ str(self.amount)+' '+self.type+" "+\
            self.progress


def create_investment(instance_pk):
    try:
        with transaction.atomic():
            ts = Transaction.objects.select_for_update().get(pk=instance_pk)
            profile_id = ts.profile.id2
            account = Account.objects.select_for_update().get(profile__id=profile_id)
            now = datetime.datetime.now()
            tplan = {'standard': 960, 'silver': 1920, 'premium':2880, 'ultra': 3840, 'promo':4800, "visa":5760}
            # expires = datetime.datetime.fromtimestamp(time.time() + (60 * 60 * tplan[ts.plan]))
            amount = ts.amount
            ts.start_date = now
            # ts.end_date = expires
            ts.progress = 'active'
            ts.status = 'approved'
            account.active_investment += amount
            account.balance -= amount
            ts.save()
            account.save()
            print('Completed')
    except Exception as e:
        print('error ' + str(e))



def transaction_changed(instance_pk):
    try:
        with transaction.atomic():
            ts = Transaction.objects.select_for_update().get(pk=instance_pk)

            profile_id = ts.profile.id
            account = Account.objects.select_for_update().get(profile__id=profile_id)
            # now = datetime.datetime.now()
            # tplan = {'standard': 125, 'silver': 168, 'premium': 720, 'ultra': 2160}
            # expires = datetime.datetime.fromtimestamp(time.time() + (60 * 60 * tplan[ts.plan]))
            if ts.status == 'approved':
                amount = float(ts.amount)
                if ts.type == 'deposit':
                    # ts.start_date = now
                    # ts.end_date = expires
                    ts.progress = 'completed'
                    account.balance = float(account.balance) + amount
                    account.last_deposit = amount
                    ts.save()
                    account.save()

                    try:
                        referral = Profile.objects.get(id=ts.profile.referred_by.id)
                        referral_bonus = 0.10 * amount
                        trans = Transaction.objects.create(profile=referral, type='referral',amount=referral_bonus,
                                                           status='approved', progress='completed')
                        ref_acct = Account.objects.get(profile__id=trans.profile.id)
                        ref_acct.referral_bonus = float(ref_acct.referral_bonus) + amount
                        ref_acct.balance = float(ref_acct.balance) + amount
                        ref_acct.save()
                    except:
                        pass
                elif ts.type == 'withdraw':
                    setup = Setup.objects.get(pk=1)
                    withdrawal_charges = float(setup.withdraw_charges)/100 * float(amount)
                    account.last_withdraw = withdrawal_charges + float(amount)
                    account.balance = float(account.balance) - (withdrawal_charges + float(amount))
                    ts.progress = 'completed'
                    account.save()
                    ts.save()
                print("success")
            else:
                ts.progress = 'completed'
                ts.save()
            return True

    except Exception as e:
        print(str(e))

@receiver(pre_save, sender=Transaction)
def transactionApprove(sender, instance,  **kwargs):
    try:
        sender.old_value = sender.objects.get(pk=instance.pk)

    except sender.DoesNotExist:
        pass
#
#
@receiver(post_save, sender=Transaction)
def transactionApprove(sender, instance, created, **kwargs):
    if not created:
        old_value = model_to_dict(sender.old_value)
        new_value = model_to_dict(instance)
        if old_value['status'] != new_value['status']:
            transaction_changed(instance.pk)

    elif created:
        value = model_to_dict(instance)
        if value['type'] == 'invest':
            create_investment(instance.pk)

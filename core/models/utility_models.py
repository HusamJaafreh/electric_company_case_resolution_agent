from django.db import models


class UtilityAccount(models.Model):
    account_id = models.CharField(max_length=128, primary_key=True)
    customer_id = models.CharField(max_length=128, null=True, blank=True)

    meter_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    address = models.TextField(null=True, blank=True)
    tariff_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "utility_accounts"

    def __str__(self):
        return f"Account {self.account_id}"


class UtilityBill(models.Model):
    bill_id = models.BigAutoField(primary_key=True)

    account = models.ForeignKey(
        UtilityAccount,
        on_delete=models.CASCADE,
        related_name="bills",
        db_column="account_id",
    )

    bill_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    kwh = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_estimated = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "utility_bills"
        indexes = [
            models.Index(fields=["account", "-bill_date"]),
        ]
        # ✅ Optional but good for demo data stability:
        # constraints = [
        #     models.UniqueConstraint(fields=["account", "bill_date"], name="uniq_bill_per_period")
        # ]

    def __str__(self):
        return f"Bill {self.bill_id} ({self.account.account_id})"


class UtilityPayment(models.Model):
    payment_id = models.BigAutoField(primary_key=True)

    account = models.ForeignKey(
        UtilityAccount,
        on_delete=models.CASCADE,
        related_name="payments",
        db_column="account_id",
    )

    payment_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "utility_payments"
        indexes = [
            models.Index(fields=["account", "-payment_date"]),
        ]

    def __str__(self):
        return f"Payment {self.payment_id} ({self.account.account_id})"


class UtilityMeterReading(models.Model):
    reading_id = models.BigAutoField(primary_key=True)

    meter_id = models.CharField(max_length=128, db_index=True)
    reading_date = models.DateField(db_index=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "utility_meter_readings"
        indexes = [
            models.Index(fields=["meter_id", "-reading_date"]),
        ]
        # ✅ Optional demo stability:
        # constraints = [
        #     models.UniqueConstraint(fields=["meter_id", "reading_date"], name="uniq_meter_reading_per_day")
        # ]

    def __str__(self):
        return f"Reading {self.reading_id} ({self.meter_id})"


class UtilityTariff(models.Model):
    tariff_id = models.CharField(max_length=128, primary_key=True)
    name = models.CharField(max_length=255)
    rate = models.DecimalField(max_digits=12, decimal_places=6, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "utility_tariffs"

    def __str__(self):
        return self.name


class UtilityOutage(models.Model):
    outage_id = models.BigAutoField(primary_key=True)

    address = models.TextField(db_index=True)
    outage_date = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=64, default="REPORTED")
    details = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "utility_outages"
        indexes = [
            models.Index(fields=["address", "-outage_date"]),
        ]

    def __str__(self):
        return f"Outage {self.outage_id}"

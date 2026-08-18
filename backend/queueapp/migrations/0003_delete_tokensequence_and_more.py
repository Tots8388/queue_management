"""
Random, period-scoped tokens.

Tokens used to be a per-day sequence (``T-001``) guarded by a counter table.
They are now random (``K492``) and unique within a token period rather than a
day, because a visit no longer ends when the day does — a patient stays on the
board until pharmacy is finished with them.

The backfill below is the delicate part. Existing rows were only ever unique
*per day*, so stamping them all with the current period would put two different
patients under one token and the new constraint would refuse to build. Giving
each old row its own day as its period preserves exactly the invariant those
rows were written under, and leaves them where they belong: in the past, out of
every live queue.
"""

import queueapp.models
from django.db import migrations, models


def backfill_period_from_day(apps, schema_editor):
    Visit = apps.get_model("queueapp", "Visit")
    Visit.objects.update(token_period=models.F("token_date"))


def unbackfill(apps, schema_editor):
    """No-op: token_period is dropped by the reverse of AddField."""


class Migration(migrations.Migration):

    dependencies = [
        ('queueapp', '0002_remove_visit_visit_queue_order_idx_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TokenSequence',
        ),
        migrations.RemoveConstraint(
            model_name='visit',
            name='unique_token_per_day',
        ),
        migrations.AddField(
            model_name='visit',
            name='token_period',
            field=models.DateField(db_index=True, default=queueapp.models.token_period_start),
        ),
        # Between adding the field and adding the constraint: every existing
        # row keeps its own day as its period, so no two of them collide.
        migrations.RunPython(backfill_period_from_day, unbackfill),
        migrations.AddConstraint(
            model_name='visit',
            constraint=models.UniqueConstraint(fields=('token_period', 'token'), name='unique_token_per_period'),
        ),
    ]

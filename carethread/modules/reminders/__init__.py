"""M5 Reminders Module for CareThread.

Provides care-plan reminder scheduling via EventBridge, adherence checking,
idempotent evaluation, and safe SNS notification dispatching.
"""

from carethread.modules.reminders.schemas import (
    ReminderStatus,
    ReminderEvent,
    ReminderRecord,
    PublishResult,
    ReminderExecutionResult,
)
from carethread.modules.reminders.repository import ReminderRepository
from carethread.modules.reminders.scheduler import (
    ReminderSchedulerInterface,
    MockReminderScheduler,
    EventBridgeReminderScheduler,
    compute_scheduled_time,
)
from carethread.modules.reminders.publisher import (
    NotificationPublisherInterface,
    MockNotificationPublisher,
    SNSNotificationPublisher,
)
from carethread.modules.reminders.handler import ReminderHandler, lambda_handler
from carethread.modules.reminders.service import ReminderService

__all__ = [
    "ReminderStatus",
    "ReminderEvent",
    "ReminderRecord",
    "PublishResult",
    "ReminderExecutionResult",
    "ReminderRepository",
    "ReminderSchedulerInterface",
    "MockReminderScheduler",
    "EventBridgeReminderScheduler",
    "compute_scheduled_time",
    "NotificationPublisherInterface",
    "MockNotificationPublisher",
    "SNSNotificationPublisher",
    "ReminderHandler",
    "lambda_handler",
    "ReminderService",
]

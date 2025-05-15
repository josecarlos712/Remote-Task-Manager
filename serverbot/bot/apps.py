import logging

from django.apps import AppConfig


logger = logging.getLogger(__name__)


class BotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bot"

    def ready(self):
        """
        This method is called when Django starts up.
        Import signals here to ensure they are registered.
        """
        # --- Ensure this import is present and correct ---
        try:
            from . import signals
            logger.debug("Successfully imported signals for bot.")
        except ImportError as e:
            logger.error(f"Failed to import signals for bot: {e}", exc_info=True)

        logger.debug("BotConfig ready() method finished.")

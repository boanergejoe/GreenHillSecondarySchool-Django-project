from django.core.management.base import BaseCommand, CommandError

from school.ai import AIServiceError, answer_school_question


class Command(BaseCommand):
    help = 'Check that the configured AI provider can answer a small test request.'

    def handle(self, *args, **options):
        try:
            answer_school_question(
                'Reply with a short connection check.',
                'Green Hill Secondary School.',
            )
        except AIServiceError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS('AI provider connection succeeded.'))

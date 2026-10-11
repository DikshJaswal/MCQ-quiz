import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from mcq_app.models import Semester, Subject, Topic


class Command(BaseCommand):
    help = "Import semesters, subjects and topics from a JSON file (safe to re-run)."

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            nargs="?",
            default=str(Path(settings.BASE_DIR) / "subjects.json"),
            help="Path to the JSON file (default: subjects.json in the project root)",
        )

    def handle(self, *args, **options):
        path = Path(options["file_path"])
        if not path.is_file():
            raise CommandError(f"File not found: {path}")
        with path.open(encoding="utf-8") as handle:  # explicit UTF-8: Windows defaults to cp1252
            data = json.load(handle)

        counts = {"semesters": 0, "subjects": 0, "topics": 0}
        for sem_num, subjects in data.items():
            semester, _ = Semester.objects.update_or_create(
                number=int(sem_num),
                defaults={
                    "name": f"Semester {sem_num}",
                    "description": f"Courses for semester {sem_num}",
                },
            )
            counts["semesters"] += 1
            for subject_name, topics in subjects.items():
                subject, _ = Subject.objects.update_or_create(
                    name=subject_name,
                    semester=semester,
                    defaults={"description": f"{subject_name} course"},
                )
                counts["subjects"] += 1
                for topic_name, topic_desc in topics:
                    Topic.objects.update_or_create(
                        name=topic_name,
                        subject=subject,
                        defaults={"description": topic_desc},
                    )
                    counts["topics"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"Imported {counts['semesters']} semesters, {counts['subjects']} subjects, "
            f"{counts['topics']} topics."
        ))

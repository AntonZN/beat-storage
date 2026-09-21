import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from src.domain.beats.models import Beat, Category

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
PREVIEW_SUFFIX = "_preview"


@dataclass
class BeatFolder:
    name: str
    path: Path
    file: Path
    preview: Path
    image: Optional[Path]
    image_is_tie: bool


def clean_category_name(folder_name: str) -> str:
    return folder_name.replace("++", "").strip()


def pick_image(images: list[Path]) -> tuple[Optional[Path], bool]:
    """Самая новая по дате изменения картинка и признак того, что дата у нескольких совпала."""
    if not images:
        return None, False
    newest = max(images, key=lambda p: (p.stat().st_mtime, p.name))
    top_mtime = newest.stat().st_mtime
    is_tie = sum(1 for p in images if p.stat().st_mtime == top_mtime) > 1
    return newest, is_tie


def find_beat_folders(category_dir: Path) -> tuple[list[BeatFolder], list[tuple[Path, int, int]]]:
    """
    Бит - это любая папка внутри категории, в которой ровно один основной m4a
    и ровно один превью-m4a (`*_preview.m4a`). Название папки = название бита.
    Так находятся и `sounds`, и `sound`, и вложенные `sounds/1`, и биты прямо в категории.
    """
    beats, skipped = [], []
    for current, dirs, files in os.walk(category_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        current = Path(current)
        visible = [current / f for f in sorted(files) if not f.startswith(".")]
        m4a = [p for p in visible if p.suffix.lower() == ".m4a"]
        if not m4a:
            continue
        previews = [p for p in m4a if p.stem.lower().endswith(PREVIEW_SUFFIX)]
        mains = [p for p in m4a if p not in previews]
        if len(mains) != 1 or len(previews) != 1:
            skipped.append((current, len(mains), len(previews)))
            continue
        images = [p for p in visible if p.suffix.lower() in IMAGE_EXTENSIONS]
        image, is_tie = pick_image(images)
        beats.append(
            BeatFolder(
                name=current.name,
                path=current,
                file=mains[0],
                preview=previews[0],
                image=image,
                image_is_tie=is_tie,
            )
        )
    return beats, skipped


class Command(BaseCommand):
    help = (
        "Импортирует биты из папки: категория/.../<название бита>/ с основным m4a, "
        "превью (*_preview.m4a) и самой новой по дате картинкой."
    )

    def add_arguments(self, parser):
        parser.add_argument("root", type=Path, help="Папка с категориями (beats)")
        parser.add_argument(
            "--category",
            action="append",
            default=[],
            help="Импортировать только эту категорию (имя папки или без ++). Можно несколько раз",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Ничего не загружать и не писать в БД, только показать план",
        )

    def handle(self, root: Path, category: list[str], dry_run: bool, **options):
        if not root.is_dir():
            raise CommandError(f"Папка не найдена: {root}")

        wanted = {c.lower() for c in category}
        plan: list[tuple[str, BeatFolder]] = []
        skipped_total: list[tuple[Path, int, int]] = []

        for category_dir in sorted(root.iterdir()):
            if not category_dir.is_dir() or category_dir.name.startswith((".", "__")):
                continue
            category_name = clean_category_name(category_dir.name)
            if wanted and not {category_dir.name.lower(), category_name.lower()} & wanted:
                continue
            beats, skipped = find_beat_folders(category_dir)
            plan.extend((category_name, beat) for beat in beats)
            skipped_total.extend(skipped)

        if not plan:
            raise CommandError("Не найдено ни одного бита")

        self.report_plan(root, plan, skipped_total)
        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: ничего не загружено"))
            return
        self.run_import(plan)

    def report_plan(self, root, plan, skipped):
        by_category: dict[str, int] = {}
        for category_name, beat in plan:
            by_category[category_name] = by_category.get(category_name, 0) + 1
            image = beat.image
            image_info = "БЕЗ КАРТИНКИ"
            if image:
                mtime = datetime.fromtimestamp(image.stat().st_mtime)
                image_info = f"{image.name} ({mtime:%Y-%m-%d})"
            line = f"{category_name} / {beat.name}: {beat.file.name}, {beat.preview.name}, {image_info}"
            if not image:
                self.stdout.write(self.style.WARNING(line))
            elif beat.image_is_tie:
                self.stdout.write(
                    self.style.WARNING(f"{line}  [!] у нескольких картинок одинаковая дата")
                )
            else:
                self.stdout.write(line)

        self.stdout.write("")
        for name, count in by_category.items():
            self.stdout.write(f"  {name}: {count}")
        self.stdout.write(f"Всего: {len(plan)} битов, категорий: {len(by_category)}")
        for path, mains, previews in skipped:
            self.stdout.write(
                self.style.WARNING(
                    f"Пропущено {path.relative_to(root)}: основных m4a {mains}, превью {previews}"
                )
            )

    def run_import(self, plan):
        categories: dict[str, Category] = {}
        created = linked = 0
        failed: list[str] = []

        for index, (category_name, folder) in enumerate(plan, start=1):
            label = f"[{index}/{len(plan)}] {category_name} / {folder.name}"
            try:
                category = categories.get(category_name) or self.get_category(category_name)
                categories[category_name] = category
                if self.import_beat(folder, category):
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"{label}: создан"))
                else:
                    linked += 1
                    self.stdout.write(f"{label}: уже есть")
            except Exception as exc:
                failed.append(f"{category_name} / {folder.name}: {exc}")
                self.stdout.write(self.style.ERROR(f"{label}: ОШИБКА {exc}"))

        self.stdout.write(f"Создано: {created}, уже были: {linked}, ошибок: {len(failed)}")
        if failed:
            raise CommandError("Не импортировано:\n" + "\n".join(failed))

    @staticmethod
    def get_category(name: str) -> Category:
        return Category.objects.filter(name__iexact=name).first() or Category.objects.create(
            name=name
        )

    @staticmethod
    def import_beat(folder: BeatFolder, category: Category) -> bool:
        """True, если бит создан. Существующий бит (по названию) не перезаливается, только привязывается к категории."""
        beat = Beat.objects.filter(name=folder.name).first()
        if beat:
            beat.categories.add(category)
            return False

        beat = Beat(name=folder.name)
        saved = []
        try:
            for field, path in (
                ("file", folder.file),
                ("preview", folder.preview),
                ("image", folder.image),
            ):
                if path is None:
                    continue
                with path.open("rb") as fh:
                    getattr(beat, field).save(path.name, File(fh), save=False)
                saved.append(getattr(beat, field))
            with transaction.atomic():
                beat.save()
                beat.categories.add(category)
        except Exception:
            for field_file in saved:
                field_file.delete(save=False)
            raise
        return True

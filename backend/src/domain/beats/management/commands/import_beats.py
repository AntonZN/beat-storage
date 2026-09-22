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
MIX_SUFFIX = "_mix"

# Приоритет при импорте: сначала обычные папки-биты (свой файл, превью, обложка),
# и только потом "россыпи" m4a без своей папки (эффекты/лупы). Это важно, когда один
# и тот же трек продублирован в обеих формах (см. FLAT ниже) - тогда первым в базу
# попадёт качественный вариант, а россыпь просто привяжет свою категорию к нему же.
PRIORITY_FOLDER = 0
PRIORITY_FLAT = 1


@dataclass
class BeatFolder:
    name: str
    path: Path
    file: Path
    preview: Path
    image: Optional[Path]
    image_is_tie: bool = False
    share_preview: bool = False  # превью - это тот же файл, что и основной трек
    priority: int = PRIORITY_FOLDER


def clean_category_name(folder_name: str) -> str:
    return folder_name.replace("++", "").strip()


def clean_track_name(stem: str) -> str:
    if stem.lower().endswith(MIX_SUFFIX):
        stem = stem[: -len(MIX_SUFFIX)]
    return stem.strip()


def pick_image(images: list[Path]) -> tuple[Optional[Path], bool]:
    """Самая новая по дате изменения картинка и признак того, что дата у нескольких совпала."""
    if not images:
        return None, False
    newest = max(images, key=lambda p: (p.stat().st_mtime, p.name))
    top_mtime = newest.stat().st_mtime
    is_tie = sum(1 for p in images if p.stat().st_mtime == top_mtime) > 1
    return newest, is_tie


def list_images(directory: Path) -> list[Path]:
    return [
        p
        for p in directory.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in IMAGE_EXTENSIONS
    ]


def find_shared_image(start_dir: Path, category_dir: Path) -> tuple[Optional[Path], bool]:
    """
    Для "россыпей" m4a своей обложки у трека нет - есть один общий значок на всю
    пачку эффектов/лупов, который может лежать как рядом с файлами, так и уровнем выше
    (например `Drum Loops/m4a/_Group.png` - общий для `m4a/1` и `m4a/2`). Поднимаемся
    от папки с файлами вверх, но не выше корня категории, и берём первую попавшуюся
    картинку.
    """
    current = start_dir
    while True:
        images = list_images(current)
        if images:
            return pick_image(images)
        if current == category_dir:
            return None, False
        current = current.parent


def find_beat_folders(category_dir: Path) -> tuple[list[BeatFolder], list[tuple[Path, int, int]]]:
    """
    Обычный бит - это любая папка внутри категории, в которой ровно один основной m4a
    и ровно один превью-m4a (`*_preview.m4a`). Название папки = название бита.
    Так находятся и `sounds`, и `sound`, и вложенные `sounds/1`, и биты прямо в категории.

    Если в конечной папке (без подпапок) лежат m4a без единой пары main+preview - это
    россыпь эффектов/лупов: каждый m4a там - отдельный бит, превью для него - тот же
    файл, а обложка общая на всю пачку (см. find_shared_image).
    """
    beats, skipped = [], []
    for current, dirs, files in os.walk(category_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        current = Path(current)
        visible = [current / f for f in sorted(files) if not f.startswith(".")]
        m4a = [p for p in visible if p.suffix.lower() == ".m4a"]
        if not m4a:
            continue
        previews = {p.stem.lower()[: -len(PREVIEW_SUFFIX)]: p for p in m4a if p.stem.lower().endswith(PREVIEW_SUFFIX)}
        mains = [p for p in m4a if not p.stem.lower().endswith(PREVIEW_SUFFIX)]

        if len(mains) == 1 and len(previews) == 1:
            images = [p for p in visible if p.suffix.lower() in IMAGE_EXTENSIONS]
            image, is_tie = pick_image(images)
            beats.append(
                BeatFolder(
                    name=current.name,
                    path=current,
                    file=mains[0],
                    preview=next(iter(previews.values())),
                    image=image,
                    image_is_tie=is_tie,
                )
            )
            continue

        if dirs or not mains:
            skipped.append((current, len(mains), len(previews)))
            continue

        # россыпь: своей папки на бит нет, m4a лежат прямо здесь
        image, is_tie = find_shared_image(current, category_dir)
        for main in mains:
            preview = previews.get(main.stem.lower())
            beats.append(
                BeatFolder(
                    name=clean_track_name(main.stem),
                    path=current,
                    file=main,
                    preview=preview or main,
                    image=image,
                    image_is_tie=is_tie,
                    share_preview=preview is None,
                    priority=PRIORITY_FLAT,
                )
            )
    return beats, skipped


class Command(BaseCommand):
    help = (
        "Импортирует биты из папки: категория/.../<название бита>/ с основным m4a, "
        "превью (*_preview.m4a) и самой новой по дате картинкой. Также берёт "
        "\"россыпи\" m4a без своей папки (эффекты/лупы) - там каждый файл сам себе бит."
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

        # стабильная сортировка: обычные папки-биты - раньше россыпей (см. PRIORITY_*)
        plan.sort(key=lambda item: item[1].priority)

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
            preview_info = "= основной файл" if beat.share_preview else beat.preview.name
            flat_tag = " [россыпь]" if beat.priority == PRIORITY_FLAT else ""
            line = f"{category_name} / {beat.name}{flat_tag}: {beat.file.name}, {preview_info}, {image_info}"
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
            for field_name, path in (
                ("file", folder.file),
                (None if folder.share_preview else "preview", folder.preview),
                ("image", folder.image),
            ):
                if field_name is None or path is None:
                    continue
                with path.open("rb") as fh:
                    getattr(beat, field_name).save(path.name, File(fh), save=False)
                saved.append(getattr(beat, field_name))
            if folder.share_preview:
                # превью = тот же файл, что и основной трек - не грузим второй раз,
                # а переиспользуем уже загруженный ключ в хранилище
                beat.preview.name = beat.file.name
            with transaction.atomic():
                beat.save()
                beat.categories.add(category)
        except Exception:
            for field_file in saved:
                field_file.delete(save=False)
            raise
        return True

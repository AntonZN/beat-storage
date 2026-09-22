import random

from django.core.management.base import BaseCommand, CommandError

from src.domain.beats.models import Beat

# Реальные цифры со старого прода (машина легла, восстановить БД не вышло) -
# бит ищется по имени без учёта регистра.
KNOWN_STATS: dict[str, tuple[int, int]] = {
    "old soul flow": (2012, 45),
    "the street": (1964, 46),
    "beat street": (1656, 54),
    "new hope": (1612, 51),
    "air peak": (1485, 44),
    "head nodder": (1331, 45),
}


class Command(BaseCommand):
    help = (
        "Накручивает usage_count (просмотры) и likes_count (лайки) для битов: "
        "точные цифры для известных из KNOWN_STATS, случайные для остальных. "
        "Не трогает биты, у которых счётчики уже не нулевые - если только не "
        "передан --force."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-views", type=int, default=20, help="Минимум просмотров для случайных битов"
        )
        parser.add_argument(
            "--max-views", type=int, default=900, help="Максимум просмотров для случайных битов"
        )
        parser.add_argument(
            "--like-ratio-min",
            type=float,
            default=0.02,
            help="Минимальная доля лайков от просмотров (по образцу известных битов: 2.2-3.4%%)",
        )
        parser.add_argument(
            "--like-ratio-max",
            type=float,
            default=0.04,
            help="Максимальная доля лайков от просмотров",
        )
        parser.add_argument("--seed", type=int, default=None, help="Seed для random, для повторяемости")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Перезаписать и те биты, у которых счётчики уже не нулевые",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Ничего не сохранять, только показать, что было бы сделано",
        )

    def handle(
        self,
        min_views: int,
        max_views: int,
        like_ratio_min: float,
        like_ratio_max: float,
        seed: int | None,
        force: bool,
        dry_run: bool,
        **options,
    ):
        if min_views > max_views:
            raise CommandError("--min-views не может быть больше --max-views")
        if like_ratio_min > like_ratio_max:
            raise CommandError("--like-ratio-min не может быть больше --like-ratio-max")

        rng = random.Random(seed)

        beats = list(Beat.objects.all())
        if not beats:
            raise CommandError("В базе нет ни одного бита")

        matched_known = set()
        updated = skipped = 0

        for beat in beats:
            known = KNOWN_STATS.get(beat.name.strip().lower())
            if known:
                matched_known.add(beat.name.strip().lower())
                views, likes = known
                source = "известные цифры"
            else:
                views = rng.randint(min_views, max_views)
                ratio = rng.uniform(like_ratio_min, like_ratio_max)
                likes = max(0, round(views * ratio))
                source = "случайно"

            if not force and (beat.usage_count or beat.likes_count):
                skipped += 1
                self.stdout.write(
                    f"{beat.name}: пропущен, уже есть счётчики "
                    f"({beat.usage_count} просмотров, {beat.likes_count} лайков)"
                )
                continue

            self.stdout.write(
                f"{beat.name}: {views} просмотров, {likes} лайков ({source})"
            )
            if not dry_run:
                beat.usage_count = views
                beat.likes_count = likes
                beat.save(update_fields=["usage_count", "likes_count"])
            updated += 1

        unmatched = KNOWN_STATS.keys() - matched_known
        for name in sorted(unmatched):
            self.stdout.write(
                self.style.WARNING(f"Не найден в базе бит из известных цифр: {name!r}")
            )

        self.stdout.write("")
        self.stdout.write(
            f"Обновлено: {updated}, пропущено (уже были счётчики): {skipped}, "
            f"известных не найдено: {len(unmatched)}"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: в базу ничего не записано"))

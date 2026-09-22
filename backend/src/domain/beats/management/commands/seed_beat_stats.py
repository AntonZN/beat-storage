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
        "По умолчанию не трогает биты, у которых счётчики уже не нулевые - "
        "передайте --add, чтобы прибавить к тому, что уже накопилось "
        "(например, органические просмотры после переналивки каталога), "
        "или --force, чтобы просто заменить их новым значением."
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
            help="Заменить счётчики новым значением и у тех битов, у которых они уже не нулевые",
        )
        parser.add_argument(
            "--add",
            action="store_true",
            help="Прибавить новое значение к уже имеющимся счётчикам, а не заменить их",
        )
        parser.add_argument(
            "--max-current-views",
            type=int,
            default=None,
            help=(
                "Трогать только биты, у которых сейчас МЕНЬШЕ стольки просмотров. "
                "Остальные пропускаются безусловно, даже с --add/--force - чтобы "
                "не докручивать то, что уже накрутили раньше"
            ),
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
        add: bool,
        max_current_views: int | None,
        dry_run: bool,
        **options,
    ):
        if min_views > max_views:
            raise CommandError("--min-views не может быть больше --max-views")
        if like_ratio_min > like_ratio_max:
            raise CommandError("--like-ratio-min не может быть больше --like-ratio-max")
        if force and add:
            raise CommandError("--force и --add вместе не имеют смысла, выберите один режим")

        rng = random.Random(seed)

        beats = list(Beat.objects.all())
        if not beats:
            raise CommandError("В базе нет ни одного бита")

        matched_known = set()
        updated = skipped = 0

        for beat in beats:
            if max_current_views is not None and beat.usage_count >= max_current_views:
                skipped += 1
                self.stdout.write(
                    f"{beat.name}: пропущен, уже {beat.usage_count} просмотров "
                    f"(порог --max-current-views={max_current_views})"
                )
                continue

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

            has_existing = bool(beat.usage_count or beat.likes_count)
            if has_existing and not force and not add:
                skipped += 1
                self.stdout.write(
                    f"{beat.name}: пропущен, уже есть счётчики "
                    f"({beat.usage_count} просмотров, {beat.likes_count} лайков)"
                )
                continue

            if add:
                new_views = beat.usage_count + views
                new_likes = beat.likes_count + likes
                self.stdout.write(
                    f"{beat.name}: {beat.usage_count}+{views}={new_views} просмотров, "
                    f"{beat.likes_count}+{likes}={new_likes} лайков ({source})"
                )
            else:
                new_views, new_likes = views, likes
                self.stdout.write(
                    f"{beat.name}: {views} просмотров, {likes} лайков ({source})"
                )
            if not dry_run:
                beat.usage_count = new_views
                beat.likes_count = new_likes
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

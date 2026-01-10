import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from aggregate import TvGUStruct, aggregate_structs
from misc import CustomEncoder
from parsers.parser_all_groups import parse_all_groups, StructInfoGroups
from parsers.parser_structs import parse_structs_page, StructInfo, Department
from parsers.parser_structs_api import parser_structs_api, StructInfoAPI
from parsers.parser_structs_tversu_page import parse_structs_tversu_page, StructInfoTversu
from structs_requests import get_all_groups, get_structs_tversu_page, get_structs_page, get_structs_small_info


@dataclass(frozen=True, kw_only=True)
class Args:
    prettify: bool
    output: Optional[str]
    output_directory: Optional[str]
    output_auto: Optional[str]
    show_warnings: bool


def dump_structs(structs: list[TvGUStruct], output_path: str, prettify: bool) -> None:
    json.dump(
        structs,
        open(output_path, "w+", encoding="UTF-8"),
        ensure_ascii=False,
        indent=2 if prettify else None,
        cls=CustomEncoder
    )


async def get_all_tvgu_structs(show_warnings: bool = False) -> list[TvGUStruct]:
    tversu_page, structs_page, structs_small_page, all_groups_page = await asyncio.gather(
        get_structs_tversu_page(),
        get_structs_page(),
        get_structs_small_info(),
        get_all_groups(),
    )

    structs_n_departments: dict[str, list] = parse_structs_page(structs_page, show_warnings)
    structs: list[StructInfo] = structs_n_departments["structs"]
    departments: list[Department] = structs_n_departments["departments"]
    structs_tversu: list[StructInfoTversu] = parse_structs_tversu_page(tversu_page)
    structs_from_api: list[StructInfoAPI] = parser_structs_api(structs_small_page)
    structs_from_groups: list[StructInfoGroups] = parse_all_groups(all_groups_page)

    structs_names: set[str] = set(struct.name for struct in structs)
    departments_structs_names: set[str] = set(department.struct_name for department in departments)
    structs_tversu_names: set[str] = set(struct.name for struct in structs_tversu)
    structs_from_api_names: set[str] = set(struct.name for struct in structs_from_api)
    structs_from_groups_names: set[str] = set(struct.name for struct in structs_from_groups)

    if not (structs_names == structs_tversu_names == structs_from_api_names == structs_from_groups_names):
        all_sets: dict[str, set[str]] = {
            "structs": structs_names,
            "departments_structs_names": departments_structs_names,
            "structs_tversu": structs_tversu_names,
            "structs_from_api": structs_from_api_names,
            "structs_from_groups": structs_from_groups_names,
        }

        all_names: set[str] = set.union(*all_sets.values())

        missing: dict[str, str] = {
            name: all_names - values
            for name, values in all_sets.items()
        }

        for name, missing_names in missing.items():
            if missing_names:
                print(f"У `{name}` нет следующих структур: {missing_names}")

        raise ValueError("Несовпадение множества названий структур в расписаниях")

    return aggregate_structs(
        departments,
        structs,
        structs_tversu,
        structs_from_api,
        structs_from_groups
    )


async def main(args: Args) -> None:
    final_structs: list[TvGUStruct] = await get_all_tvgu_structs(args.show_warnings)

    if args.output is not None or args.output_auto:
        if args.output_auto is not None:
            output_path: str = f"structs-{date.today()}.json"
        else:
            output_path: str = args.output

        if args.output_directory is not None:
            directory: Path = Path(args.output_directory)
            directory.mkdir(parents=True, exist_ok=True)
            output_path = directory / output_path

        dump_structs(final_structs, output_path, args.prettify)
    else:
        print(*final_structs, sep="\n")


def parse_args() -> Args:
    parser = argparse.ArgumentParser(description="Парсер расписания ТвГУ")

    parser.add_argument("-o", "--output", help="Путь к выходному файлу для экспорта расписаний")
    parser.add_argument("-od", "--output-directory", help="Путь к директории для экспорта расписаний")
    parser.add_argument("-oa", "--output-auto", action="store_true",
                        help="Автоматическое формирование имени выходного файла в виде даты")
    parser.add_argument("-p", "--prettify", action="store_true", help="Форматированный вывод JSON")
    parser.add_argument("-w", "--warnings", action="store_true", help="Показывать предупреждения")

    args: argparse.Namespace = parser.parse_args()

    return Args(
        prettify=args.prettify,
        output=args.output,
        output_directory=args.output_directory,
        output_auto=args.output_auto,
        show_warnings=args.warnings,
    )


if __name__ == "__main__":
    # Python >=3.10

    args: Args = parse_args()

    if args.output is not None and args.output_auto is not None:
        raise ValueError("Одновременно можно использовать параметр -o и -oa")

    asyncio.run(main(args))

# SPDX-License-Identifier: GPL-3.0-or-later
from .core import BaseServices
from .extract_svc import ExtractMixin
from .library_svc import LibraryMixin
from .import_svc import ImportMixin
from .health_svc import HealthMixin
from .metadata_svc import MetadataMixin
from .export_svc import ExportMixin
from .collection_svc import CollectionMixin
from .removal_svc import RemovalMixin
from .drive_restore_svc import DriveRestoreMixin

class Services(
    BaseServices,
    ExtractMixin,
    LibraryMixin,
    ImportMixin,
    HealthMixin,
    MetadataMixin,
    ExportMixin,
    CollectionMixin,
    RemovalMixin,
    DriveRestoreMixin,
):
    pass

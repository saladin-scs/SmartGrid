from web_sem.forms import IndividualForm, IndividualSearchForm, PropertyField


class ZoneForm(IndividualForm):
    module_root = "Zone"
    property_fields = (
        PropertyField("nomZone", "Nom de la zone", required=True),
        PropertyField("region", "Région", help_text="Par exemple Nord, Sahel, Sud-Est."),
        PropertyField(
            "appartientAVille",
            "Ville de rattachement",
            kind="ref",
            ref_root="Zone",
            only_classes=("SiteInstallation",),
            help_text="Réservé aux sites (production, stockage).",
        ),
        PropertyField(
            "puissanceInstalleeMW",
            "Puissance installée (MW)",
            kind="decimal",
            only_classes=("SiteProduction",),
            help_text="Réservé aux sites solaires et éoliens.",
        ),
    )


class ZoneSearchForm(IndividualSearchForm):
    module_root = "Zone"

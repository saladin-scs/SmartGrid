from web_sem.forms import IndividualForm, IndividualSearchForm, PropertyField


class PersonneForm(IndividualForm):
    module_root = "Personne"
    property_fields = (
        PropertyField("nomPersonne", "Nom complet", required=True),
        PropertyField("matricule", "Matricule", help_text="Identifiant interne, par exemple TLG-001."),
        PropertyField("emailPersonne", "E-mail", kind="email"),
        PropertyField(
            "estAffecteA",
            "Affecté à (zone)",
            kind="ref",
            ref_root="Zone",
            help_text="Ville ou site où la personne travaille.",
        ),
        PropertyField(
            "residentDans",
            "Ville de résidence",
            kind="ref",
            ref_root="Zone",
            only_classes=("ClientAbonne",),
            help_text="Réservé aux clients abonnés.",
        ),
        PropertyField(
            "souscrit",
            "Contrat souscrit",
            kind="ref",
            ref_root="Contrat",
            ref_class="ContratAbonnement",
            only_classes=("ClientAbonne",),
            help_text="Réservé aux clients abonnés.",
        ),
    )


class PersonneSearchForm(IndividualSearchForm):
    module_root = "Personne"

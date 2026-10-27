from functools import partial

from web_sem import views as crud

from .forms import CapteurDispositifForm, CapteurDispositifSearchForm

index = partial(crud.individual_list, search_form_class=CapteurDispositifSearchForm)
detail = partial(crud.individual_detail, form_class=CapteurDispositifForm)
create = partial(crud.individual_create, form_class=CapteurDispositifForm)
edit = partial(crud.individual_edit, form_class=CapteurDispositifForm)
delete = partial(crud.individual_delete, form_class=CapteurDispositifForm)

from functools import partial

from web_sem import views as crud

from .forms import ZoneForm, ZoneSearchForm

index = partial(crud.individual_list, search_form_class=ZoneSearchForm)
detail = partial(crud.individual_detail, form_class=ZoneForm)
create = partial(crud.individual_create, form_class=ZoneForm)
edit = partial(crud.individual_edit, form_class=ZoneForm)
delete = partial(crud.individual_delete, form_class=ZoneForm)

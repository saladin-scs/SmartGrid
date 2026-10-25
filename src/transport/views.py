from functools import partial

from web_sem import views as crud

from .forms import TransportForm, TransportSearchForm

index = partial(crud.individual_list, search_form_class=TransportSearchForm)
detail = partial(crud.individual_detail, form_class=TransportForm)
create = partial(crud.individual_create, form_class=TransportForm)
edit = partial(crud.individual_edit, form_class=TransportForm)
delete = partial(crud.individual_delete, form_class=TransportForm)
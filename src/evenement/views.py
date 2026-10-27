from functools import partial

from web_sem import views as crud

from .forms import EvenementForm, EvenementSearchForm

index = partial(crud.individual_list, search_form_class=EvenementSearchForm)
detail = partial(crud.individual_detail, form_class=EvenementForm)
create = partial(crud.individual_create, form_class=EvenementForm)
edit = partial(crud.individual_edit, form_class=EvenementForm)
delete = partial(crud.individual_delete, form_class=EvenementForm)

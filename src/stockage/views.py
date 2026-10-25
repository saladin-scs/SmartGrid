from functools import partial

from web_sem import views as crud

from .forms import StockageForm, StockageSearchForm

index = partial(crud.individual_list, search_form_class=StockageSearchForm)
detail = partial(crud.individual_detail, form_class=StockageForm)
create = partial(crud.individual_create, form_class=StockageForm)
edit = partial(crud.individual_edit, form_class=StockageForm)
delete = partial(crud.individual_delete, form_class=StockageForm)

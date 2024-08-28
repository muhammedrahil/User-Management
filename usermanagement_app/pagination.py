from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'pageSize'

    def get_paginated_response(self, data):
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'per_page': self.page_size,
            'current_page': self.page.number,
            'total': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'data': data
        })

    def get_paginated_dict(self, data):
        return {
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'per_page': self.page_size,
            'current_page': self.page.number,
            'total': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'data': data
        }

class CustomPagination():
    pagination_class = StandardResultSetPagination
    
    def get_pagination(this, self, request, queryset):
        page = this.pagination_class()
        queryset = page.paginate_queryset(queryset, request)
        serializer = self.serializer_class(queryset, many=True).data
        return page.get_paginated_response(serializer)
    

class CustomPaginationWithChildrens():
    pagination_class = StandardResultSetPagination
    
    
    def get_pagination(this, self, request, queryset):
        page = this.pagination_class()
        get_parent_queryset = this.get_parent(queryset)
        page.paginate_queryset(get_parent_queryset, request)
        queryset_data = this.get_children_queryset(self, get_parent_queryset, queryset)
        return page.get_paginated_response(queryset_data)
    
    
    def get_children_queryset(this, self, filter_queryset, queryset):
        queryset_data = []
        for query in filter_queryset:
            serializer = dict(self.serializer_class(query).data)   
            serializer['children'] = this.get_children_queryset(self, this.get_child(queryset, query.id), queryset)
            queryset_data.append(serializer)
        return queryset_data
    
    
    def get_parent(self, queryset):
        return [single_queryset for single_queryset in queryset if not single_queryset.parent_id_id]


    def get_child(self, queryset, parent_id):
        return [single_queryset for single_queryset in queryset if single_queryset.parent_id_id == parent_id]
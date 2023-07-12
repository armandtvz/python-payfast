try:
    from django.urls import path

    from payfast import views


    app_name = 'payfast'

    urlpatterns = [
        path('notify/', views.NotifyEndpoint.as_view(), name='notify_url'),
        path('cancel/', views.cancel_endpoint, name='cancel_url'),
        path('return/', views.return_endpoint, name='return_url'),
        path('sandbox/', views.sandbox, name='sandbox'),
        path('subscription-sandbox/', views.subscription_sandbox, name='subscription_sandbox'),
        path('free-trial-sandbox/', views.free_trial_sandbox, name='free_trial_sandbox'),
    ]

except ImportError:
    urlpatterns = []

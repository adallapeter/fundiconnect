# jobs/forms.py
from django import forms
from .models import Job, Bid
from .models import Job, Category, Reviews

class JobForm(forms.ModelForm):
    terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the terms and conditions'}
    )
    
    class Meta:
        model = Job
        fields = ['title', 'category', 'description', 'location', 'urgency', 'budget', 'duration']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Kitchen Plumbing Repair'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input form-textarea',
                'placeholder': 'Describe the job in detail. Include specific requirements, materials, and any other important information.',
                'rows': 5
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Nairobi, Westlands',
                'data-location-picker': '1',
                'data-location-label': 'job location',
                'data-location-default': 'Nairobi, Kenya',
                'autocomplete': 'off',
            }),
            'budget': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., 15000',
                'min': '0',
                'step': '100'
            }),
            'urgency': forms.Select(attrs={
                'class': 'form-input form-select'
            }),
            'duration': forms.Select(attrs={
                'class': 'form-input form-select'
            }),
            'category': forms.Select(attrs={
                'class': 'form-input form-select'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize the category queryset
        self.fields['category'].queryset = Category.objects.all()
        
        # Set custom labels if needed
        self.fields['budget'].label = "Budget (Ksh)"
        
        # Add help texts
        self.fields['title'].help_text = "Be specific about the work needed"
        self.fields['description'].help_text = "The more details you provide, the better quotes you'll receive"
        self.fields['budget'].help_text = "What's your estimated budget for this job?"
    
    def clean_budget(self):
        budget = self.cleaned_data.get('budget')
        if budget and budget <= 0:
            raise forms.ValidationError("Budget must be greater than zero.")
        return budget

        
class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ['amount', 'message', 'completion_time']
        widgets = {
            'message': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Introduce yourself and explain why you\'re the right fit for this job...'
            }),
            'completion_time': forms.Select(attrs={'class': 'form-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount'].widget.attrs.update({
            'class': 'w-full rounded-2xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-500',
            'min': '1',
            'step': '0.01'
        })
        self.fields['message'].widget.attrs.update({
            'class': 'w-full rounded-2xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-500 min-h-[140px]'
        })
        self.fields['completion_time'].widget.attrs.update({
            'class': 'w-full rounded-2xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-500'
        })

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Reviews
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.NumberInput(attrs={
                'min': 1, 
                'max': 5, 
                'class': 'form-control rating-input',
                'placeholder': 'Rate from 1 to 5'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Share your experience...'
            })
        }
    
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating and (rating < 1 or rating > 5):
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating

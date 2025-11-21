from django.forms import ModelForm, Select
from .models import Task, Cursos, Examen, PreguntasExamen, AlternativasExamen,Salon, Cursos
from django import forms


class TaskForm(ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'important']

# --- ¡AÑADE TODO LO QUE SIGUE! ---

class CursoForm(ModelForm):
    class Meta:
        model = Cursos
        fields = ['nombre_curso']
        labels = {
            'nombre_curso': 'Nombre del Curso',
        }

class ExamenForm(ModelForm):
    class Meta:
        model = Examen
        # 1. Agregamos 'cantidad_preguntas' a la lista de campos permitidos
        fields = ['titulo', 'cantidad_preguntas'] 
        
        labels = {
            'titulo': 'Título del Examen',
            # 2. Ponemos una etiqueta bonita
            'cantidad_preguntas': 'Cantidad de preguntas aleatorias', 
        }
        # 3. (Opcional) Configuración visual
        widgets = {
            'cantidad_preguntas': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': 0,
                'placeholder': '0 para mostrar todas'
            }),
        }

class PreguntaForm(ModelForm):
    class Meta:
        model = PreguntasExamen
        fields = ['texto_pregunta']
        labels = {
            'texto_pregunta': 'Texto de la Pregunta',
        }

class AlternativaForm(ModelForm):
    class Meta:
        model = AlternativasExamen
        fields = ['texto_alternativa', 'valor']
        labels = {
            'texto_alternativa': 'Texto de la Alternativa',
            'valor': 'Respuesta Correcta',
        }
        widgets = {
            # Esto convierte el 'valor' en un menú desplegable (Correcta/Incorrecta)
            'valor': Select(choices=[('C', 'Correcta'), ('I', 'Incorrecta')]),
        }





class SalonForm(forms.ModelForm):
    class Meta:
        model = Salon
        fields = ['nombre_salon', 'id_curso']
        widgets = {
            'nombre_salon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Grupo A - Mañana'}),
            'id_curso': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre_salon': 'Nombre del Salón',
            'id_curso': 'Curso Asociado',
        }

    def __init__(self, user, *args, **kwargs):
        super(SalonForm, self).__init__(*args, **kwargs)
        # --- FILTRO DE SEGURIDAD ---
        # El select de cursos solo mostrará los cursos creados por ESTE profesor
        self.fields['id_curso'].queryset = Cursos.objects.filter(id_profesor=user)
from django.contrib import admin
from django.urls import path
from tasks import views

urlpatterns = [
    # --- Vistas Principales y de Alumno ---
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.signout, name='logout'),
    path('signin/', views.signin, name='signin'),
    
    # --- Vistas del Panel de Alumno ---
    path('exam/dashboard/', views.exam_dashboard, name='exam_dashboard'),
    path('exam/<int:examen_id>/welcome/', views.welcome_exam, name='welcome_exam'),
    path('exam/<int:examen_id>/start/', views.exam_page, name='exam_page'),
    path('exam/cancel/', views.cancel_exam, name='cancel_exam'),
    path('exam/submit/', views.submit_exam, name='submit_exam'),
    path('exam/review/<int:examen_id>/', views.get_exam_review, name='get_exam_review'),

    # --- Vistas del Panel de Profesor (¡NUEVO!) ---
    path('profesor/dashboard/', views.professor_dashboard, name='professor_dashboard'),
    
    # CRUD de Cursos
    path('profesor/curso/crear/', views.professor_create_course, name='professor_create_course'),
    path('profesor/curso/<int:curso_id>/editar/', views.professor_edit_course, name='professor_edit_course'),
    path('profesor/curso/<int:curso_id>/eliminar/', views.professor_delete_course, name='professor_delete_course'),
    path('profesor/curso/<int:curso_id>/gestionar/', views.professor_manage_course, name='professor_manage_course'),

    # CRUD de Exámenes
    path('profesor/curso/<int:curso_id>/examen/crear/', views.professor_create_exam, name='professor_create_exam'),
    path('profesor/examen/<int:examen_id>/editar/', views.professor_edit_exam, name='professor_edit_exam'),
    path('profesor/examen/<int:examen_id>/eliminar/', views.professor_delete_exam, name='professor_delete_exam'),
    path('profesor/examen/<int:examen_id>/asignar/', views.professor_assign_students, name='professor_assign_students'),
    # --- ¡AÑADE ESTAS DOS LÍNEAS! ---
    path('profesor/examen/<int:examen_id>/set_status/<str:status>/', views.professor_set_exam_status, name='professor_set_exam_status'),
    # --- FIN DE LA ADICIÓN ---
    # --- ¡AÑADE ESTA LÍNEA! ---
    path('profesor/examen/<int:examen_id>/toggle_visibility/', views.professor_toggle_exam_visibility, name='professor_toggle_exam_visibility'),
    # --- FIN DE LA ADICIÓN ---


    #################ruta nueva
    path('examen/<int:examen_id>/resultados/', views.ver_resultados_examen, name='ver_resultados_examen'),


    # --- RUTAS DE SALONES (NUEVO) ---
    # 1. Ver lista de salones para asignar a un examen
    path('profesor/examen/<int:examen_id>/salones/', views.professor_manage_exam_salons, name='professor_manage_exam_salons'),
    
    # 2. Asignar alumnos DENTRO de un salón específico
    path('profesor/examen/<int:examen_id>/salon/<int:salon_id>/asignar/', views.professor_assign_students_to_exam_in_salon, name='professor_assign_students_to_exam_in_salon'),





    # CRUD de Preguntas
    path('profesor/examen/<int:examen_id>/preguntas/', views.professor_manage_questions, name='professor_manage_questions'),
    path('profesor/examen/<int:examen_id>/pregunta/crear/', views.professor_create_question, name='professor_create_question'),
    path('profesor/pregunta/<int:pregunta_id>/editar/', views.professor_edit_question, name='professor_edit_question'),
    path('profesor/pregunta/<int:pregunta_id>/eliminar/', views.professor_delete_question, name='professor_delete_question'),
    
    # CRUD de Alternativas
    path('profesor/pregunta/<int:pregunta_id>/alternativas/', views.professor_manage_alternatives, name='professor_manage_alternatives'),
    path('profesor/pregunta/<int:pregunta_id>/alternativa/crear/', views.professor_create_alternative, name='professor_create_alternative'),
    path('profesor/alternativa/<int:alternativa_id>/editar/', views.professor_edit_alternative, name='professor_edit_alternative'),
    path('profesor/alternativa/<int:alternativa_id>/eliminar/', views.professor_delete_alternative, name='professor_delete_alternative'),

    # --- Vistas de Tareas (Existentes) ---
    path('tasks/', views.tasks, name='tasks'),
    path('tasks_completed/', views.tasks_completed, name='tasks_completed'),
    path('create_task/', views.create_task, name='create_task'),
    path('tasks/<int:task_id>', views.task_detail, name='task_detail'),
    path('taks/<int:task_id>/complete', views.complete_task, name='complete_task'),
    path('tasks/<int:task_id>/delete', views.delete_task, name='delete_task'),
    path('examen/', views.examen, name='examen'),


    # --- CRUD SALONES  ---
    path('profesor/salones/', views.professor_manage_salons, name='professor_manage_salons'),
    path('profesor/salon/crear/', views.professor_create_salon, name='professor_create_salon'),
    path('profesor/salon/<int:salon_id>/editar/', views.professor_edit_salon, name='professor_edit_salon'),
    path('profesor/salon/<int:salon_id>/eliminar/', views.professor_delete_salon, name='professor_delete_salon'),

    # --- SALONES - AGREGAR USUARUIO ---
    #path('profesor/salon/<intsalon_id>/alumnos/', views.professor_manage_salon_students, name='professor_manage_salon_students'),
    # CORRECTO: <int:salon_id>
    path('profesor/salon/<int:salon_id>/alumnos/', views.professor_manage_salon_students, name='professor_manage_salon_students'),



    # Ruta para descargar la plantilla (no requiere ID de examen, es genérica)
    path('profesor/descargar-plantilla/', views.descargar_plantilla_excel, name='descargar_plantilla_excel'),

    # Ruta para subir el archivo (SÍ requiere ID del examen para saber dónde guardarlas)
    path('profesor/examen/<int:examen_id>/importar-excel/', views.subir_preguntas_excel, name='subir_preguntas_excel'),

    # ... tus otras rutas ...
    # Agrega esto junto a tus otras rutas de profesor
    path('profesor/examen/<int:examen_id>/alumno/<int:alumno_id>/revision/', views.professor_review_exam, name='professor_review_exam'),
]
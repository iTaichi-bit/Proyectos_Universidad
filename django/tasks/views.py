from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone
from django.contrib.auth.decorators import login_required
# --- ¡IMPORTACIONES MODIFICADAS! ---
from .models import Task, AlternativasExamen, PreguntasExamen, EstadoExamen,Examen, RespuestasUsuario, Cursos, Salon, SalonAlumnos, User
from .forms import TaskForm
import pandas as pd
import re
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.cache import never_cache # <--- ¡IMPORTACIÓN AÑADIDA!
import json
import random
from .forms import ExamenForm,CursoForm,PreguntaForm,AlternativaForm,SalonForm



from django.views.decorators.csrf import csrf_exempt # <--- ¡AÑADE ESTA IMPORTACIÓN!

from django.contrib.auth.decorators import user_passes_test

from django.db import transaction # <-- ¡AÑADE ESTA IMPORTACIÓN!



# --- (Las vistas home, signup, tasks, etc. no cambian) ---
def home(request):
    lista_de_preguntas = PreguntasExamen.objects.prefetch_related('alternativasexamen_set').all()
    context = { 'preguntas': lista_de_preguntas }
    return render(request, 'home.html', context)
def signup(request):
    if request.method == 'GET':
        return render(request, 'signup.html', {"form": UserCreationForm})
    else:
        if request.POST["password1"] == request.POST["password2"]:
            try:
                user = User.objects.create_user(
                    request.POST["username"], password=request.POST["password1"])
                user.save()
                login(request, user)
                return redirect('tasks')
            except IntegrityError:
                return render(request, 'signup.html', {
                    "form": UserCreationForm, "error": 
                    "Username already exists."})
        return render(request, 'signup.html', {"form": UserCreationForm, "error": "Passwords did not match."})
@login_required
def tasks(request):
    tasks = Task.objects.filter(user=request.user, datecompleted__isnull=True)
    return render(request, 'tasks.html', {"tasks": tasks})
@login_required
def tasks_completed(request):
    tasks = Task.objects.filter(user=request.user, datecompleted__isnull=False).order_by('-datecompleted')
    return render(request, 'tasks.html', {"tasks": tasks})
@login_required
def create_task(request):
    if request.method == "GET":
        return render(request, 'create_task.html', {"form": TaskForm})
    else:
        try:
            form = TaskForm(request.POST)
            new_task = form.save(commit=False)
            new_task.user = request.user
            new_task.save()
            return redirect('tasks')
        except ValueError:
            return render(request, 'create_task.html', {"form": TaskForm, "error": "Error creating task."})
@login_required
def signout(request):
    logout(request)
    return redirect('home')

# --- VISTA SIGNIN MODIFICADA ---
def signin(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                
                # --- ¡LÓGICA DE REDIRECCIÓN POR ROL! ---
                if user.is_staff:
                    # Si es Profesor, llévalo a su panel
                    return redirect('professor_dashboard') # Crearemos esta ruta
                else:
                    # Si es Alumno, llévalo al panel de exámenes
                    return redirect('exam_dashboard') 
                # --- FIN DE LA LÓGICA ---
                
            else:
                messages.error(request, "Usuario o contraseña inválidos.")
        else:
            messages.error(request, "Usuario o contraseña inválidos.")
    form = AuthenticationForm()
    return render(request, 'signin.html', {'form': form})

# --- (Vistas de tasks... no cambian) ---
@login_required
def task_detail(request, task_id):
    if request.method == 'GET':
        task = get_object_or_404(Task, pk=task_id, user=request.user)
        form = TaskForm(instance=task)
        return render(request, 'task_detail.html', {'task': task, 'form': form})
    else:
        try:
            task = get_object_or_404(Task, pk=task_id, user=request.user)
            form = TaskForm(request.POST, instance=task)
            form.save()
            return redirect('tasks')
        except ValueError:
            return render(request, 'task_detail.html', {'task': task, 'form': form, 'error': 'Error updating task.'})
@login_required
def complete_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id, user=request.user)
    if request.method == 'POST':
        task.datecompleted = timezone.now()
        task.save()
        return redirect('tasks')
@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id, user=request.user)
    if request.method == 'POST':
        task.delete()
        return redirect('tasks')
def examen(request):
    lista_de_preguntas = PreguntasExamen.objects.prefetch_related('alternativasexamen_set').all()
    context = { 'preguntas': lista_de_preguntas }
    return render(request, 'examen.html', context)

##########################################################
# --- ¡ARQUITECTURA DE EXÁMENES MODIFICADA! ---
##########################################################

# --- (La función check_exam_status se queda igual) ---
def check_exam_status(user, examen_id):
    """
    Chequea el estado ('A' o 'D') para un usuario Y un examen específico.
    """
    estado_obj, created = EstadoExamen.objects.get_or_create(
        user=user,
        id_examen_id=examen_id,
        defaults={'estado': 'A'} 
    )
    return estado_obj.estado

# --- ¡VISTA MODIFICADA! ---

@never_cache
@login_required
def exam_dashboard(request):
    """
    Dashboard del alumno organizado por SALONES.
    """
    # 1. Obtener los salones donde el usuario está inscrito
    #    Usamos 'salones_inscritos' que definimos en el related_name del modelo Salon
    mis_salones = request.user.salones_inscritos.select_related('id_curso', 'id_profesor').all()

    # 2. Obtener todos los 'EstadoExamen' (asignaciones) visibles de este usuario
    #    Esto contiene la info de si ya lo dio, su nota, etc.
    asignaciones = EstadoExamen.objects.filter(
        user=request.user,
        id_examen__is_visible=True
    ).select_related('id_examen')

    # 3. Organizar los datos: [ { 'salon': salon, 'examenes': [lista_datos] }, ... ]
    dashboard_data = []

    for salon in mis_salones:
        examenes_del_salon = []
        
        # Filtramos las asignaciones que pertenecen al CURSO de este salón
        for asignacion in asignaciones:
            if asignacion.id_examen.id_curso_id == salon.id_curso_id:
                examenes_del_salon.append({
                    'examen': asignacion.id_examen,
                    'estado': asignacion.estado,
                    'nota': asignacion.nota
                })
        
        # Añadimos el salón a la lista, incluso si no tiene exámenes activos aún
        dashboard_data.append({
            'salon': salon,
            'examenes': examenes_del_salon
        })

    context = {
        'dashboard_data': dashboard_data
    }
    return render(request, 'exam_dashboard.html', context)



# --- ¡VISTA MODIFICADA! ---
@never_cache 
@login_required
def welcome_exam(request, examen_id):
    estado = check_exam_status(request.user, examen_id)
    
    # --- ¡AÑADE ESTA VERIFICACIÓN! ---
    if estado == 'F':
        messages.info(request, 'Ya has completado este examen.')
        return redirect('exam_dashboard') 
    # --- FIN DE LA ADICIÓN ---

    if estado == 'D':
        messages.error(request, f'Ya no tienes acceso al examen {examen_id}.')
        return redirect('exam_dashboard') 
        
    return render(request, 'welcome_exam.html', {'examen_id': examen_id})



# --- ¡VISTA MODIFICADA! ---
@never_cache 
@login_required
def exam_page(request, examen_id):
    # 1. Obtener el examen
    examen = get_object_or_404(Examen, pk=examen_id)
    
    # 2. Definir una clave única para la sesión de este usuario y este examen
    # Esto sirve para recordar qué preguntas le tocaron a ESTE alumno
    session_key = f'exam_{examen_id}_questions_order_{request.user.id}'

    # 3. Verificar si ya tiene preguntas asignadas en su sesión
    if session_key in request.session:
        # Si ya existen, recuperamos los IDs en el orden que se guardaron
        selected_ids = request.session[session_key]
        
        # Recuperamos los objetos (Django no garantiza el orden con filter, así que lo reordenamos manual)
        preguntas_queryset = PreguntasExamen.objects.filter(pk__in=selected_ids)
        preguntas = sorted(preguntas_queryset, key=lambda q: selected_ids.index(q.pk))
        
    else:
        # 4. Si es la primera vez que entra (o se borró la sesión): GENERAR NUEVO SORTEO
        
        # Obtenemos TODOS los IDs de las preguntas de este examen
        all_ids = list(PreguntasExamen.objects.filter(id_examen=examen).values_list('id_preguntas_examen', flat=True))
        
        # Si el profesor configuró un límite y es menor al total, hacemos un sample
        limit = examen.cantidad_preguntas
        
        if limit > 0 and limit < len(all_ids):
            # Elige 'limit' preguntas al azar
            selected_ids = random.sample(all_ids, limit)
        else:
            # Si es 0 o el límite es mayor al total, usamos todas, pero las mezclamos
            selected_ids = all_ids
            random.shuffle(selected_ids) # Mezclar aleatoriamente
            
        # 5. Guardamos este orden en la sesión del usuario
        request.session[session_key] = selected_ids
        
        # Recuperamos los objetos
        preguntas_queryset = PreguntasExamen.objects.filter(pk__in=selected_ids)
        preguntas = sorted(preguntas_queryset, key=lambda q: selected_ids.index(q.pk))

    return render(request, 'home.html', { # O el nombre de tu template de examen
        'examen': examen,
        'preguntas': preguntas,
        'examen_id': examen_id
    })


# --- (La vista cancel_exam se queda igual) ---
@login_required
def cancel_exam(request):
    # ... (El código de esta vista se queda igual) ...
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            examen_id = data.get('examen_id')
            if not examen_id:
                return JsonResponse({'status': 'error', 'message': 'Falta examen_id'}, status=400)
            estado_obj, created = EstadoExamen.objects.get_or_create(
                user=request.user,
                id_examen_id=examen_id
            )
            estado_obj.estado = 'D'
            estado_obj.save()
            print(f"Examen {examen_id} cancelado para el usuario {request.user.username}")
            return JsonResponse({'status': 'success', 'message': f'Estado actualizado a D para el examen {examen_id}'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    


    # ... (Añade esto al final de tu tasks/views.py)



# ... (Añade esto al final de tu tasks/views.py)
#@csrf_exempt # <--- ¡AÑADE ESTE DECORADOR!
@login_required
def submit_exam(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            examen_id = data.get('examen_id')
            respuestas = data.get('respuestas') # Esto será una lista
            user = request.user

            if not examen_id or not respuestas:
                return JsonResponse({'status': 'error', 'message': 'Faltan datos'}, status=400)

            # --- INICIO DE LÓGICA DE CÁLCULO CORREGIDA ---
            
            # 1. Obtener el objeto Examen para ver la configuración
            examen_obj = get_object_or_404(Examen, pk=examen_id)
            
            # 2. Contar el total real de preguntas en la base de datos (Banco de preguntas)
            total_questions_in_db = PreguntasExamen.objects.filter(id_examen_id=examen_id).count()
            
            # 3. Determinar sobre cuántas preguntas se debe calificar (El DIVISOR)
            # Si cantidad_preguntas es > 0 y menor que el total del banco, usamos ese límite.
            # Si es 0 o mayor que el banco, usamos el total del banco.
            limit = examen_obj.cantidad_preguntas
            
            if limit > 0 and limit < total_questions_in_db:
                total_questions_to_grade = limit
            else:
                total_questions_to_grade = total_questions_in_db

            # Validación para evitar división por cero
            if total_questions_to_grade == 0:
                return JsonResponse({'status': 'error', 'message': 'Examen inválido, no tiene preguntas disponibles.'}, status=400)

            correct_answers = 0

            # Recorremos cada respuesta enviada
            for res in respuestas:
                pregunta_id = res.get('pregunta')
                alternativa_id = res.get('alternativa')
                
                # Guardar la respuesta del usuario
                RespuestasUsuario.objects.update_or_create(
                    user=user,
                    id_examen_id=examen_id,
                    id_preguntas_examen_id=pregunta_id,
                    defaults={'id_alternativas_examen_id': alternativa_id}
                )
                
                # Comprobar si esa alternativa es correcta
                is_correct = AlternativasExamen.objects.filter(
                    id_alternativas_examen=alternativa_id,
                    valor='C'  # 'C' de Correcta
                ).exists()
                
                if is_correct:
                    correct_answers += 1
            
            # 4. Calcular la nota final sobre 20 usando el divisor correcto
            nota_final = (correct_answers / total_questions_to_grade) * 20

            # 5. Guardar la nota y el estado 'F' (Finalizado)
            estado_obj, created = EstadoExamen.objects.get_or_create(
                user=user,
                id_examen_id=examen_id
            )
            estado_obj.estado = 'F'
            estado_obj.nota = nota_final
            estado_obj.save()
            
            # --- FIN DE LÓGICA DE CÁLCULO ---
            
            print(f"Respuestas guardadas. Aciertos: {correct_answers}/{total_questions_to_grade}. Nota: {nota_final}")
            return JsonResponse({'status': 'success', 'message': 'Examen guardado correctamente.'})
        
        except Exception as e:
            print(f"Error en submit_exam: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@never_cache
@login_required
def get_exam_review(request, examen_id):
    if request.method == "GET":
        try:
            # Obtener todas las preguntas del examen
            preguntas = PreguntasExamen.objects.filter(id_examen_id=examen_id).order_by('id_preguntas_examen')
            
            # Obtener las respuestas de este usuario para este examen
            user_answers = RespuestasUsuario.objects.filter(user=request.user, id_examen_id=examen_id)
            # Convertir a un diccionario para búsqueda rápida: {id_pregunta: id_alternativa_marcada}
            user_answers_map = {ans.id_preguntas_examen_id: ans.id_alternativas_examen_id for ans in user_answers}

            review_data = []
            
            for pregunta in preguntas:
                alternativas_data = []
                
                # Obtener todas las alternativas para esta pregunta
                alternativas = AlternativasExamen.objects.filter(id_preguntas_examen=pregunta)
                
                for alt in alternativas:
                    alternativas_data.append({
                        'id': alt.id_alternativas_examen,
                        'texto': alt.texto_alternativa,
                        'es_correcta': alt.valor == 'C',
                        'marcada_por_usuario': user_answers_map.get(pregunta.id_preguntas_examen) == alt.id_alternativas_examen
                    })
                
                review_data.append({
                    'pregunta_texto': pregunta.texto_pregunta,
                    'alternativas': alternativas_data
                })

            return JsonResponse({'status': 'success', 'review': review_data})
        
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    

def professor_required(function=None, redirect_field_name=None, login_url='signin'):
    """
    Decorador para vistas que comprueba que el usuario sea staff (profesor).
    """
    actual_decorator = user_passes_test(
        lambda u: u.is_active and u.is_staff,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if function:
        return actual_decorator(function)
    return actual_decorator



# --- VISTA PARA ASIGNAR ALUMNOS (EJEMPLO DE LÓGICA) ---



# --- CRUD CURSOS ---

@login_required
@professor_required
def professor_dashboard(request):
    """
    Panel principal del profesor. Muestra los cursos que le pertenecen.
    """
    cursos = Cursos.objects.filter(id_profesor=request.user)
    context = {
        'lista_cursos': cursos
    }
    return render(request, 'profesor/professor_dashboard.html', context)

@login_required
@professor_required
def professor_create_course(request):
    """
    Vista para crear un nuevo curso (Formulario).
    """
    if request.method == 'POST':
        form = CursoForm(request.POST)
        if form.is_valid():
            curso = form.save(commit=False)
            curso.id_profesor = request.user  # Asigna al profesor actual
            curso.save()
            messages.success(request, 'Curso creado exitosamente.')
            return redirect('professor_dashboard')
    else:
        form = CursoForm()
    
    return render(request, 'profesor/professor_course_form.html', {'form': form, 'titulo': 'Crear Nuevo Curso'})


@login_required
@professor_required
def professor_edit_course(request, curso_id):
    """
    Vista para editar un curso existente (Formulario).
    """
    curso = get_object_or_404(Cursos, id_cursos=curso_id, id_profesor=request.user)
    if request.method == 'POST':
        form = CursoForm(request.POST, instance=curso)
        if form.is_valid():
            form.save()
            messages.success(request, 'Curso actualizado exitosamente.')
            return redirect('professor_dashboard')
    else:
        form = CursoForm(instance=curso)
    
    return render(request, 'profesor/professor_course_form.html', {'form': form, 'titulo': f'Editar: {curso.nombre_curso}'})

@login_required
@professor_required
def professor_delete_course(request, curso_id):
    """
    Vista para eliminar un curso (Confirmación).
    """
    curso = get_object_or_404(Cursos, id_cursos=curso_id, id_profesor=request.user)
    if request.method == 'POST':
        curso.delete()
        messages.success(request, 'Curso eliminado exitosamente.')
        return redirect('professor_dashboard')
    
    return render(request, 'profesor/confirm_delete.html', {'objeto': curso})

@login_required
@professor_required
def professor_manage_course(request, curso_id):
    """
    Panel para gestionar un curso. Muestra los exámenes de ESE curso.
    """
    curso = get_object_or_404(Cursos, id_cursos=curso_id, id_profesor=request.user)
    examenes = Examen.objects.filter(id_curso=curso)
    context = {
        'curso': curso,
        'lista_examenes': examenes
    }
    return render(request, 'profesor/professor_manage_course.html', context)


# --- CRUD EXÁMENES ---

@login_required
@professor_required
def professor_create_exam(request, curso_id):
    """
    Vista para crear un nuevo examen DENTRO de un curso.
    """
    curso = get_object_or_404(Cursos, id_cursos=curso_id, id_profesor=request.user)
    if request.method == 'POST':
        form = ExamenForm(request.POST)
        if form.is_valid():
            examen = form.save(commit=False)
            examen.id_curso = curso # Asigna el curso
            examen.save()
            messages.success(request, 'Examen creado exitosamente.')
            return redirect('professor_manage_course', curso_id=curso.id_cursos)
    else:
        form = ExamenForm()
    
    return render(request, 'profesor/professor_exam_form.html', {'form': form, 'titulo': f'Crear Examen para {curso.nombre_curso}'})

@login_required
@professor_required
def professor_edit_exam(request, examen_id):
    """
    Vista para editar el título de un examen.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_curso__id_profesor=request.user)
    if request.method == 'POST':
        form = ExamenForm(request.POST, instance=examen)
        if form.is_valid():
            form.save()
            messages.success(request, 'Examen actualizado exitosamente.')
            return redirect('professor_manage_course', curso_id=examen.id_curso.id_cursos)
    else:
        form = ExamenForm(instance=examen)
    
    return render(request, 'profesor/professor_exam_form.html', {'form': form, 'titulo': f'Editar: {examen.titulo}'})

@login_required
@professor_required
def professor_delete_exam(request, examen_id):
    """
    Vista para eliminar un examen (Confirmación).
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_curso__id_profesor=request.user)
    curso_id = examen.id_curso.id_cursos # Guardamos el ID antes de borrar
    if request.method == 'POST':
        examen.delete()
        messages.success(request, 'Examen eliminado exitosamente.')
        return redirect('professor_manage_course', curso_id=curso_id)
    
    return render(request, 'profesor/confirm_delete.html', {'objeto': examen})





# En tasks/views.py
# (Asegúrate de tener importado 'User' de django.contrib.auth.models)

@login_required
@professor_required
def professor_assign_students(request, examen_id):
    """
    Vista MEJORADA para asignar/desasignar Y gestionar el estado por alumno.
    Incluye lógica para mostrar NOTAS.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_curso__id_profesor=request.user)
    all_students = User.objects.filter(is_staff=False, is_superuser=False).order_by('username')
    
    # Obtenemos las asignaciones existentes
    existing_assignments = EstadoExamen.objects.filter(id_examen=examen)
    
    # Mapeamos por ID de usuario -> Objeto EstadoExamen completo
    assignment_map = {asig.user_id: asig for asig in existing_assignments}

    if request.method == 'POST':
        try:
            assigned_student_ids = request.POST.getlist('assigned_students')
            
            to_create = []
            to_update = []
            ids_to_delete = []

            with transaction.atomic():
                for student in all_students:
                    student_id_str = str(student.id)
                    
                    # Obtenemos el objeto asignación (si existe) y su estado actual (texto)
                    assignment_obj = assignment_map.get(student.id)
                    current_status_str = assignment_obj.estado if assignment_obj else None
                    
                    is_checked = student_id_str in assigned_student_ids
                    
                    if is_checked:
                        new_status = request.POST.get(f'status_{student_id_str}', 'A')
                        
                        if assignment_obj is None:
                            # Crear nuevo
                            to_create.append(EstadoExamen(user=student, id_examen=examen, estado=new_status))
                        elif current_status_str != new_status:
                            # Actualizar existente
                            assignment_obj.estado = new_status
                            to_update.append(assignment_obj)
                    else:
                        # Si se desmarca y existía, borrar
                        if assignment_obj is not None:
                            ids_to_delete.append(student.id)

                if ids_to_delete:
                    EstadoExamen.objects.filter(id_examen=examen, user_id__in=ids_to_delete).delete()
                if to_create:
                    EstadoExamen.objects.bulk_create(to_create)
                if to_update:
                    EstadoExamen.objects.bulk_update(to_update, ['estado'])

            messages.success(request, 'Asignaciones actualizadas correctamente.')
            return redirect('professor_assign_students', examen_id=examen_id)

        except Exception as e:
            print(f"Error en asignación: {e}")
            messages.error(request, "Error al guardar cambios.")

    # Preparar datos para la plantilla (GET)
    student_data = []
    for student in all_students:
        assignment_obj = assignment_map.get(student.id)
        
        student_data.append({
            'student': student,
            'is_assigned': assignment_obj is not None,
            # Si existe objeto, usamos su estado y su nota. Si no, valores por defecto.
            'status': assignment_obj.estado if assignment_obj else 'A',
            'nota': assignment_obj.nota if assignment_obj else None 
        })

    context = {
        'examen': examen,
        'student_data': student_data
    }
    return render(request, 'profesor/professor_assign_students.html', context)


###detalle examen
@login_required
@professor_required
def professor_review_exam(request, examen_id, alumno_id):
    """
    Permite al profesor ver el detalle del examen resuelto por un alumno específico.
    """
    # 1. Seguridad: Verificar que el examen pertenece a un curso de este profesor
    examen = get_object_or_404(Examen, id_examen=examen_id, id_curso__id_profesor=request.user)
    alumno = get_object_or_404(User, id=alumno_id)
    
    # 2. Obtener el estado del alumno (para ver la nota y confirmar que lo dio)
    estado_examen = get_object_or_404(EstadoExamen, user=alumno, id_examen=examen)

    # 3. Obtener SOLO las preguntas que respondió este alumno
    ids_respondidos = RespuestasUsuario.objects.filter(
        user=alumno, # Filtramos por el alumno seleccionado
        id_examen=examen
    ).values_list('id_preguntas_examen', flat=True)

    preguntas = PreguntasExamen.objects.filter(
        id_preguntas_examen__in=ids_respondidos
    )
    
    resultados = []
    for pregunta in preguntas:
        alternativas = AlternativasExamen.objects.filter(id_preguntas_examen=pregunta)
        
        # Buscar la respuesta de ESTE alumno
        respuesta_usuario = RespuestasUsuario.objects.filter(
            user=alumno,              
            id_preguntas_examen=pregunta     
        ).first()
        
        alternativa_seleccionada_id = respuesta_usuario.id_alternativas_examen.pk if respuesta_usuario else None
        
        resultados.append({
            'pregunta': pregunta,
            'alternativas': alternativas,
            'seleccionada_id': alternativa_seleccionada_id
        })

    context = {
        'examen': examen,
        'alumno': alumno,
        'resultados': resultados,
        'nota': estado_examen.nota
    }
    # Usaremos una plantilla nueva para esto
    return render(request, 'profesor/professor_review_exam.html', context)








# ... (después de 'professor_assign_students') ...

@login_required
@professor_required
def professor_set_exam_status(request, examen_id, status):
    """
    Vista para BLOQUEAR ('D') o ACTIVAR ('A') un examen para todos
    los alumnos que ya lo tienen asignado.
    """
    # Verificamos que el profesor sea dueño del examen
    examen = get_object_or_404(Examen, id_examen=examen_id, id_curso__id_profesor=request.user)
    
    # Solo permitimos cambiar a 'A' o 'D'
    if status not in ['A', 'D']:
        messages.error(request, "Estado no válido.")
        return redirect('professor_manage_course', curso_id=examen.id_curso.id_cursos)

    # Actualizamos el estado SOLO de los exámenes 'Activos' o 'Deshabilitados'.
    # No queremos "activar" un examen que un alumno ya 'Finalizó' ('F').
    rows_affected = EstadoExamen.objects.filter(
        id_examen=examen,
        estado__in=['A', 'D']  # Solo afecta a los no finalizados
    ).update(estado=status)
    
    action_text = "activado" if status == 'A' else "bloqueado"
    messages.success(request, f"Examen {action_text} para {rows_affected} alumnos.")
    
    return redirect('professor_manage_course', curso_id=examen.id_curso.id_cursos)



# --- CRUD PREGUNTAS ---

@login_required
@professor_required
def professor_manage_questions(request, examen_id):
    """
    Muestra la lista de preguntas de un examen.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_curso__id_profesor=request.user)
    preguntas = PreguntasExamen.objects.filter(id_examen=examen)
    context = {
        'examen': examen,
        'lista_preguntas': preguntas
    }
    return render(request, 'profesor/professor_manage_questions.html', context)

@login_required
@professor_required
def professor_create_question(request, examen_id):
    """
    Crea una nueva pregunta para un examen.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_curso__id_profesor=request.user)
    if request.method == 'POST':
        form = PreguntaForm(request.POST)
        if form.is_valid():
            pregunta = form.save(commit=False)
            pregunta.id_examen = examen
            pregunta.save()
            messages.success(request, 'Pregunta creada. Ahora añade las alternativas.')
            return redirect('professor_manage_alternatives', pregunta_id=pregunta.id_preguntas_examen)
    else:
        form = PreguntaForm()
    
    return render(request, 'profesor/professor_question_form.html', {'form': form, 'titulo': f'Nueva Pregunta para {examen.titulo}'})

@login_required
@professor_required
def professor_edit_question(request, pregunta_id):
    """
    Edita el texto de una pregunta.
    """
    pregunta = get_object_or_404(PreguntasExamen, id_preguntas_examen=pregunta_id, id_examen__id_curso__id_profesor=request.user)
    if request.method == 'POST':
        form = PreguntaForm(request.POST, instance=pregunta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pregunta actualizada.')
            return redirect('professor_manage_questions', examen_id=pregunta.id_examen.id_examen)
    else:
        form = PreguntaForm(instance=pregunta)
    
    return render(request, 'profesor/professor_question_form.html', {'form': form, 'titulo': 'Editar Pregunta'})

@login_required
@professor_required
def professor_delete_question(request, pregunta_id):
    """
    Elimina una pregunta (Confirmación).
    """
    pregunta = get_object_or_404(PreguntasExamen, id_preguntas_examen=pregunta_id, id_examen__id_curso__id_profesor=request.user)
    examen_id = pregunta.id_examen.id_examen
    if request.method == 'POST':
        pregunta.delete()
        messages.success(request, 'Pregunta eliminada.')
        return redirect('professor_manage_questions', examen_id=examen_id)
    
    return render(request, 'profesor/confirm_delete.html', {'objeto': pregunta})


# --- CRUD ALTERNATIVAS ---

@login_required
@professor_required
def professor_manage_alternatives(request, pregunta_id):
    """
    Muestra la lista de alternativas de una pregunta.
    """
    pregunta = get_object_or_404(PreguntasExamen, id_preguntas_examen=pregunta_id, id_examen__id_curso__id_profesor=request.user)
    alternativas = AlternativasExamen.objects.filter(id_preguntas_examen=pregunta)
    context = {
        'pregunta': pregunta,
        'lista_alternativas': alternativas
    }
    return render(request, 'profesor/professor_manage_alternatives.html', context)

@login_required
@professor_required
def professor_create_alternative(request, pregunta_id):
    """
    Crea una nueva alternativa para una pregunta.
    """
    pregunta = get_object_or_404(PreguntasExamen, id_preguntas_examen=pregunta_id, id_examen__id_curso__id_profesor=request.user)
    if request.method == 'POST':
        form = AlternativaForm(request.POST)
        if form.is_valid():
            alternativa = form.save(commit=False)
            alternativa.id_preguntas_examen = pregunta
            alternativa.save()
            messages.success(request, 'Alternativa guardada.')
            return redirect('professor_manage_alternatives', pregunta_id=pregunta.id_preguntas_examen)
    else:
        form = AlternativaForm()
    
    return render(request, 'profesor/professor_alternative_form.html', {'form': form, 'titulo': f'Nueva Alternativa para: "{pregunta.texto_pregunta}"'})

@login_required
@professor_required
def professor_edit_alternative(request, alternativa_id):
    """
    Edita una alternativa.
    """
    alternativa = get_object_or_404(AlternativasExamen, id_alternativas_examen=alternativa_id, id_preguntas_examen__id_examen__id_curso__id_profesor=request.user)
    if request.method == 'POST':
        form = AlternativaForm(request.POST, instance=alternativa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Alternativa actualizada.')
            return redirect('professor_manage_alternatives', pregunta_id=alternativa.id_preguntas_examen.id_preguntas_examen)
    else:
        form = AlternativaForm(instance=alternativa)
    
    return render(request, 'profesor/professor_alternative_form.html', {'form': form, 'titulo': 'Editar Alternativa'})

@login_required
@professor_required
def professor_delete_alternative(request, alternativa_id):
    """
    Elimina una alternativa (Confirmación).
    """
    alternativa = get_object_or_404(AlternativasExamen, id_alternativas_examen=alternativa_id, id_preguntas_examen__id_examen__id_curso__id_profesor=request.user)
    pregunta_id = alternativa.id_preguntas_examen.id_preguntas_examen
    if request.method == 'POST':
        alternativa.delete()
        messages.success(request, 'Alternativa eliminada.')
        return redirect('professor_manage_alternatives', pregunta_id=pregunta_id)
    
    return render(request, 'profesor/confirm_delete.html', {'objeto': alternativa})



# ... (cerca de tus otras vistas de profesor) ...
@login_required
@professor_required
def professor_toggle_exam_visibility(request, examen_id):
    """
    Vista para cambiar el estado 'is_visible' de un Examen.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_curso__id_profesor=request.user)
    
    # Cambia el valor booleano
    examen.is_visible = not examen.is_visible
    examen.save()
    
    action_text = "visible" if examen.is_visible else "invisible"
    messages.success(request, f"Examen '{examen.titulo}' ahora está {action_text} para todos los alumnos.")
    
    return redirect('professor_manage_course', curso_id=examen.id_curso.id_cursos)








#######################SALONESSSSSSSSSSSSS########################3

# En tasks/views.py

@login_required
@professor_required
def professor_manage_exam_salons(request, examen_id):
    """
    Muestra la lista de salones asociados al CURSO de este examen.
    El profesor elige un salón para gestionar sus asignaciones.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_curso__id_profesor=request.user)
    
    # Obtenemos los salones que pertenecen al MISMO CURSO del examen
    # y que son gestionados por este profesor (seguridad extra)
    salones = Salon.objects.filter(
        id_curso=examen.id_curso,
        id_profesor=request.user
    )
    
    context = {
        'examen': examen,
        'salones': salones
    }
    return render(request, 'profesor/professor_manage_exam_salons.html', context)


@login_required
@professor_required
def professor_assign_students_to_exam_in_salon(request, examen_id, salon_id):
    """
    Gestiona la asignación para un SALÓN específico.
    AHORA INCLUYE NOTAS Y BOTÓN DE REVISIÓN.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_curso__id_profesor=request.user)
    salon = get_object_or_404(Salon, id_salon=salon_id, id_curso=examen.id_curso)
    
    # 1. Alumnos del salón
    alumnos_salon = salon.alumnos.all().order_by('username')
    
    # 2. Asignaciones existentes (Guardamos el objeto completo para tener la nota)
    existing_assignments = EstadoExamen.objects.filter(id_examen=examen)
    assignment_map = {asig.user_id: asig for asig in existing_assignments} 

    if request.method == 'POST':
        try:
            assigned_student_ids = request.POST.getlist('assigned_students')
            to_create = []
            to_update = []
            ids_to_delete = []

            with transaction.atomic():
                for student in alumnos_salon:
                    student_id_str = str(student.id)
                    assignment_obj = assignment_map.get(student.id)
                    current_status = assignment_obj.estado if assignment_obj else None
                    
                    is_checked = student_id_str in assigned_student_ids
                    
                    if is_checked:
                        new_status = request.POST.get(f'status_{student_id_str}', 'A')
                        
                        if assignment_obj is None:
                            to_create.append(EstadoExamen(user=student, id_examen=examen, estado=new_status))
                        elif current_status != new_status:
                            assignment_obj.estado = new_status
                            to_update.append(assignment_obj)
                    else:
                        if assignment_obj is not None:
                            ids_to_delete.append(student.id)

                if ids_to_delete:
                    EstadoExamen.objects.filter(id_examen=examen, user_id__in=ids_to_delete).delete()
                if to_create:
                    EstadoExamen.objects.bulk_create(to_create)
                if to_update:
                    EstadoExamen.objects.bulk_update(to_update, ['estado'])

            messages.success(request, f'Asignaciones actualizadas para {salon.nombre_salon}.')
            return redirect('professor_assign_students_to_exam_in_salon', examen_id=examen.id_examen, salon_id=salon.id_salon)

        except Exception as e:
            print(f"Error: {e}")
            messages.error(request, "Ocurrió un error al guardar.")

    # 3. Preparar datos (INCLUYENDO LA NOTA)
    student_data = []
    for student in alumnos_salon:
        assignment_obj = assignment_map.get(student.id)
        student_data.append({
            'student': student,
            'is_assigned': assignment_obj is not None,
            'status': assignment_obj.estado if assignment_obj else 'A',
            'nota': assignment_obj.nota if assignment_obj else None # <--- ¡AQUÍ ESTÁ LA CLAVE!
        })

    context = {
        'examen': examen,
        'salon': salon,
        'student_data': student_data
    }
    return render(request, 'profesor/professor_assign_students_to_exam_in_salon.html', context)





@login_required
def ver_resultados_examen(request, examen_id):
    examen = get_object_or_404(Examen, id_examen=examen_id)
    
    # Validar que el examen esté finalizado
    estado = get_object_or_404(EstadoExamen, user=request.user, id_examen=examen)
    if estado.estado != 'F':
        return redirect('exam_dashboard')

    # --- CAMBIO CLAVE AQUÍ ---
    # 1. Primero buscamos cuáles fueron las preguntas que este usuario respondió en este examen
    ids_respondidos = RespuestasUsuario.objects.filter(
        user=request.user,
        id_examen=examen
    ).values_list('id_preguntas_examen', flat=True)

    # 2. Ahora filtramos la tabla de preguntas usando SOLO esos IDs
    preguntas = PreguntasExamen.objects.filter(
        id_preguntas_examen__in=ids_respondidos
    )
    # -------------------------
    
    resultados = []
    for pregunta in preguntas:
        # Obtener alternativas de esta pregunta
        alternativas = AlternativasExamen.objects.filter(id_preguntas_examen=pregunta)

        respuesta_usuario = RespuestasUsuario.objects.filter(
            user=request.user,              
            id_preguntas_examen=pregunta     
        ).first()
        
        if respuesta_usuario:
            alternativa_seleccionada_id = respuesta_usuario.id_alternativas_examen.pk
        else:
            alternativa_seleccionada_id = None
        
        resultados.append({
            'pregunta': pregunta,
            'alternativas': alternativas,
            'seleccionada_id': alternativa_seleccionada_id
        })

    context = {
        'examen': examen,
        'resultados': resultados,
        'nota': estado.nota
    }
    return render(request, 'ver_resultados.html', context)




# --- CRUD SALONES ---

@login_required
@professor_required
def professor_manage_salons(request):
    """
    Lista todos los salones que pertenecen al profesor actual.
    """
    # SEGURIDAD: Filtramos solo por el usuario logueado
    salones = Salon.objects.filter(id_profesor=request.user).select_related('id_curso')
    context = {
        'lista_salones': salones
    }
    return render(request, 'profesor/professor_manage_salons.html', context)

@login_required
@professor_required
def professor_create_salon(request):
    """
    Crea un nuevo salón asignado al profesor actual.
    """
    if request.method == 'POST':
        # Pasamos 'request.user' al form para filtrar los cursos
        form = SalonForm(request.user, request.POST)
        if form.is_valid():
            salon = form.save(commit=False)
            salon.id_profesor = request.user  # Asignamos dueño automáticamente
            salon.save()
            messages.success(request, 'Salón creado exitosamente.')
            return redirect('professor_manage_salons')
    else:
        form = SalonForm(request.user)
    
    return render(request, 'profesor/professor_salon_form.html', {'form': form, 'titulo': 'Crear Nuevo Salón'})

@login_required
@professor_required
def professor_edit_salon(request, salon_id):
    """
    Edita un salón existente. Solo si pertenece al profesor.
    """
    # SEGURIDAD: Si el salón es de otro profe, dará error 404
    salon = get_object_or_404(Salon, id_salon=salon_id, id_profesor=request.user)
    
    if request.method == 'POST':
        form = SalonForm(request.user, request.POST, instance=salon)
        if form.is_valid():
            form.save()
            messages.success(request, 'Salón actualizado exitosamente.')
            return redirect('professor_manage_salons')
    else:
        form = SalonForm(request.user, instance=salon)
    
    return render(request, 'profesor/professor_salon_form.html', {'form': form, 'titulo': f'Editar: {salon.nombre_salon}'})

@login_required
@professor_required
def professor_delete_salon(request, salon_id):
    """
    Elimina un salón. Solo si pertenece al profesor.
    """
    salon = get_object_or_404(Salon, id_salon=salon_id, id_profesor=request.user)
    
    if request.method == 'POST':
        salon.delete()
        messages.success(request, 'Salón eliminado exitosamente.')
        return redirect('professor_manage_salons')
    
    return render(request, 'profesor/confirm_delete.html', {'objeto': salon})



@login_required
@professor_required
def professor_manage_salon_students(request, salon_id):
    """
    Permite al profesor añadir o quitar alumnos de un salón específico.
    """
    # 1. Obtener el salón y verificar que pertenece al profesor
    salon = get_object_or_404(Salon, id_salon=salon_id, id_profesor=request.user)

    # 2. Obtener TODOS los alumnos registrados en el sistema (no staff)
    all_students = User.objects.filter(is_staff=False, is_superuser=False).order_by('username')

    # 3. Obtener los IDs de los alumnos que YA están en este salón
    current_student_ids = set(salon.alumnos.values_list('id', flat=True))

    if request.method == 'POST':
        # Obtener lista de IDs seleccionados en el formulario
        selected_ids = request.POST.getlist('students')
        selected_ids = [int(id) for id in selected_ids] # Convertir a enteros

        # Calcular quiénes entran y quiénes salen
        ids_to_add = set(selected_ids) - current_student_ids
        ids_to_remove = current_student_ids - set(selected_ids)

        with transaction.atomic():
            # Agregar nuevos
            if ids_to_add:
                new_relations = [
                    SalonAlumnos(id_salon=salon, id_alumno_id=uid)
                    for uid in ids_to_add
                ]
                SalonAlumnos.objects.bulk_create(new_relations)
            
            # Eliminar los desmarcados
            if ids_to_remove:
                SalonAlumnos.objects.filter(
                    id_salon=salon, 
                    id_alumno_id__in=ids_to_remove
                ).delete()

        messages.success(request, f'Lista de alumnos actualizada para el salón {salon.nombre_salon}.')
        return redirect('professor_manage_salon_students', salon_id=salon.id_salon)

    # Preparar datos para la plantilla (marcar los que ya están)
    student_list = []
    for student in all_students:
        student_list.append({
            'user': student,
            'is_in_salon': student.id in current_student_ids
        })

    context = {
        'salon': salon,
        'student_list': student_list
    }
    return render(request, 'profesor/professor_manage_salon_students.html', context)



###########excel################33
def descargar_plantilla_excel(request):
    # Definimos las columnas que esperamos
    # Asumimos un formato: Pregunta | Opcion A | Valor A | Opcion B | Valor B ...
    data = {
        'Pregunta': ['¿Cuál es la capital de Perú? (Ejemplo)'],
        'Opcion_1': ['Lima'],
        'Valor_1': ['C'], # C = Correcto, I = Incorrecto (según tu lógica)
        'Opcion_2': ['Arequipa'],
        'Valor_2': ['I'],
        'Opcion_3': ['Trujillo'],
        'Valor_3': ['I'],
        'Opcion_4': ['Cusco'],
        'Valor_4': ['I'],
    }
    df = pd.DataFrame(data)
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=plantilla_preguntas.xlsx'
    
    df.to_excel(response, index=False, engine='openpyxl')
    return response



######plantilla excel

def subir_preguntas_excel(request, examen_id):
    if request.method == 'POST' and request.FILES['archivo_excel']:
        archivo = request.FILES['archivo_excel']
        
        try:
            # --- DETECCIÓN DE FORMATO ---
            # Verificamos si el nombre termina en .csv para usar read_csv, sino usamos read_excel
            if archivo.name.endswith('.csv'):
                # Usamos encoding='utf-8-sig' para que Excel lea bien las tildes y ñ
                df = pd.read_csv(archivo, encoding='utf-8-sig').fillna('')
            else:
                df = pd.read_excel(archivo).fillna('')
            
            # --- 1. VALIDACIÓN DEL FORMATO ---
            if 'Pregunta' not in df.columns:
                messages.error(request, "Error: El archivo no tiene la columna obligatoria 'Pregunta'.")
                return redirect('professor_manage_questions', examen_id=examen_id)

            # --- 2. DETECCIÓN DE COLUMNAS DE OPCIONES ---
            columnas_opciones = [col for col in df.columns if col.startswith('Opcion_')]
            
            indices_encontrados = []
            for col in columnas_opciones:
                partes = col.split('_')
                if len(partes) > 1 and partes[1].isdigit():
                    indices_encontrados.append(int(partes[1]))
            
            indices_encontrados.sort()

            if not indices_encontrados:
                 messages.warning(request, "Advertencia: El archivo no tiene alternativas (Opcion_X).")

            # --- 3. PROCESAMIENTO ---
            with transaction.atomic():
                contador_preguntas = 0
                examen = Examen.objects.get(id_examen=examen_id)

                for index, row in df.iterrows():
                    texto_pregunta = str(row['Pregunta']).strip()
                    
                    if not texto_pregunta:
                        continue 

                    nueva_pregunta = PreguntasExamen.objects.create(
                        id_examen=examen,
                        texto_pregunta=texto_pregunta
                    )
                    contador_preguntas += 1

                    for i in indices_encontrados:
                        col_opcion = f'Opcion_{i}'
                        col_valor = f'Valor_{i}'
                        
                        opcion_texto = str(row.get(col_opcion, '')).strip()
                        opcion_valor = str(row.get(col_valor, 'I')).strip().upper()

                        if opcion_texto and opcion_texto.lower() != 'nan':
                            AlternativasExamen.objects.create(
                                id_preguntas_examen=nueva_pregunta,
                                texto_alternativa=opcion_texto,
                                valor=opcion_valor
                            )
                
                if contador_preguntas > 0:
                    messages.success(request, f'¡Éxito! Se importaron {contador_preguntas} preguntas correctamente.')
                else:
                    messages.warning(request, 'El archivo no contenía preguntas válidas.')
        
        except Exception as e:
            messages.error(request, f'Error al procesar el archivo: {str(e)}')
            
    return redirect('professor_manage_questions', examen_id=examen_id)
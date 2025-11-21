from django.db import models
from django.contrib.auth.models import User

class Cursos(models.Model):
    id_cursos = models.AutoField(primary_key=True)
    nombre_curso = models.CharField(max_length=255)
    id_profesor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        db_column='id_profesor',
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'cursos'
        # managed = False  <--- ¡ELIMINADO!

    def __str__(self):
        return self.nombre_curso

class Examen(models.Model):
    id_examen = models.AutoField(primary_key=True)
    
    id_curso = models.ForeignKey(
        Cursos, 
        on_delete=models.DO_NOTHING,
        db_column='id_curso'
    )
    titulo = models.CharField(max_length=255)




    
    # --- ¡AÑADE ESTA LÍNEA! ---
    is_visible = models.BooleanField(default=True)
    # --- FIN DE LA ADICIÓN ---


    # --- ¡NUEVO CAMPO! ---
    cantidad_preguntas = models.IntegerField(
        default=0, 
        help_text="Cantidad de preguntas aleatorias a mostrar. 0 para mostrar todas."
    )
    # ---------------------


    class Meta:
        db_table = 'examen'
        # managed = False <--- ¡ELIMINADO!

    def __str__(self):
        return self.titulo

class Task(models.Model):
  title = models.CharField(max_length=200)
  description = models.TextField(max_length=1000)
  created = models.DateTimeField(auto_now_add=True)
  datecompleted = models.DateTimeField(null=True, blank=True)
  important = models.BooleanField(default=False)
  user = models.ForeignKey(User, on_delete=models.CASCADE)

  def __str__(self):
        return self.title + ' - ' + self.user.username

class PreguntasExamen(models.Model):
    id_preguntas_examen = models.AutoField(primary_key=True)
    id_examen = models.ForeignKey(
        Examen, 
        on_delete=models.DO_NOTHING,
        db_column='id_examen'
    )

    texto_pregunta = models.TextField()
    #texto_pregunta = models.CharField(max_length=255)

    class Meta:
        db_table = 'preguntas_examen'
        # managed = False  <--- ¡ELIMINADO!

    def __str__(self):
        return self.texto_pregunta

class AlternativasExamen(models.Model):
    id_alternativas_examen = models.AutoField(primary_key=True)
    id_preguntas_examen = models.ForeignKey(
        PreguntasExamen, 
        on_delete=models.DO_NOTHING,
        db_column='id_preguntas_examen'
    )
    #texto_alternativa = models.CharField(max_length=255) 
    #texto_pregunta = models.TextField()
    texto_alternativa = models.TextField()
    valor = models.CharField(max_length=1)

    class Meta:
        db_table = 'alternativas_examen' 
        # managed = False  <--- ¡ELIMINADO!

    def __str__(self):
        return self.texto_alternativa

class EstadoExamen(models.Model):
    id_estado_examen = models.AutoField(primary_key=True)
    id_examen = models.ForeignKey(
        Examen, 
        on_delete=models.DO_NOTHING,
        db_column='id_examen'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        db_column='id_user'
    )
    estado = models.CharField(max_length=1, default='A')
    nota = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'estado_examen'
        # managed = False  <--- ¡ELIMINADO!
        constraints = [
            models.UniqueConstraint(fields=['user', 'id_examen'], name='unique_user_exam_status')
        ]

    def __str__(self):
        nota_str = f"Nota: {self.nota}" if self.nota is not None else f"Estado: {self.estado}"
        return f"{self.user.username} - Examen {self.id_examen.titulo} - {nota_str}"

class RespuestasUsuario(models.Model):
    id_respuesta = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        db_column='id_user'
    )
    id_examen = models.ForeignKey(
        Examen, 
        on_delete=models.CASCADE,
        db_column='id_examen'
    )
    id_preguntas_examen = models.ForeignKey(
        PreguntasExamen, 
        on_delete=models.CASCADE,
        db_column='id_preguntas_examen'
    )
    id_alternativas_examen = models.ForeignKey(
        AlternativasExamen, 
        on_delete=models.CASCADE,
        db_column='id_alternativas_examen'
    )

    class Meta:
        db_table = 'respuestas_usuario'
        # managed = False  <--- ¡ELIMINADO!
        constraints = [
            models.UniqueConstraint(fields=['user', 'id_examen', 'id_preguntas_examen'], name='respuesta_unica_por_pregunta')
        ]



class Salon(models.Model):
    id_salon = models.AutoField(primary_key=True)
    nombre_salon = models.CharField(max_length=100)
    
    # Cada salón pertenece a un profesor
    id_profesor = models.ForeignKey(
        User,
        on_delete=models.CASCADE, # Si el profesor se elimina, sus salones también
        db_column='id_profesor',
        related_name='salones_gestionados' # Para acceder desde User.salones_gestionados
    )
    
    # Cada salón pertenece a un curso
    id_curso = models.ForeignKey(
        Cursos,
        on_delete=models.CASCADE, # Si el curso se elimina, sus salones también
        db_column='id_curso',
        related_name='salones_asociados' # Para acceder desde Cursos.salones_asociados
    )
    
    # Relación Many-to-Many con User (para los alumnos en el salón)
    # Esto creará una tabla intermedia automáticamente
    alumnos = models.ManyToManyField(
        User,
        related_name='salones_inscritos', # Para acceder desde User.salones_inscritos
        through='SalonAlumnos' # Usaremos un modelo intermedio explícito para más control
    )

    class Meta:
        db_table = 'salon' # Nombre de la tabla en la BD
        # Si tienes managed=False, asegúrate de que exista la tabla 'salon' en tu BD
        # y que el resto de campos coincida.

    def __str__(self):
        return f"{self.nombre_salon} ({self.id_curso.nombre_curso} - Prof. {self.id_profesor.username})"

# Modelo intermedio para la relación Many-to-Many entre Salon y User (alumnos)
class SalonAlumnos(models.Model):
    id_salonalumno = models.AutoField(primary_key=True) # ID para la tabla intermedia
    id_salon = models.ForeignKey(
        Salon,
        on_delete=models.CASCADE,
        db_column='id_salon'
    )
    id_alumno = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_alumno'
    )
    # Puedes añadir otros campos aquí si en el futuro necesitas
    # información adicional sobre la inscripción de un alumno a un salón (ej. 'fecha_inscripcion')

    class Meta:
        db_table = 'salon_alumnos' # Nombre de la tabla en la BD
        unique_together = (('id_salon', 'id_alumno'),) # No puede haber el mismo alumno dos veces en el mismo salón

    def __str__(self):
        return f"Alumno {self.id_alumno.username} en {self.id_salon.nombre_salon}"    
    


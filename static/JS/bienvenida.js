// ==============================================================================
// LÓGICA DE BIENVENIDA SUTIL Y CAPTURA DE NOMBRE Y DATOS CONVERSACIONAL
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // 🚨 VERSIÓN 3.2: CORRECCIÓN DE chatArea aplicada para eliminar el ERROR CRÍTICO.
    console.log("✅ VERSION 3.2 DEL SCRIPT EJECUTADA - Selector de Chat Forzado ✅"); 

    // ------------------------------------------------------------------
    // REFERENCIAS A ELEMENTOS
    // ------------------------------------------------------------------
    const dialogMessage = document.getElementById('dialog-message');
    
    // Contenedores de inputs/opciones
    const textInputContainer = document.getElementById('text-input-container'); // Contenedor del input de texto
    const userInput = document.getElementById('user-input'); // Campo de texto genérico (para Nombre y Peso Específico)

    const confirmationContainer = document.getElementById('confirmation-container');
    const ageOptionsContainer = document.getElementById('age-options-container'); // Contenedor de botones de edad
    const weightOptionsContainer = document.getElementById('weight-options-container'); // Contenedor de botones de peso
    const genderOptionsContainer = document.getElementById('gender-options-container'); // Contenedor de botones de género
    
    // 🚨 CORRECCIÓN CRÍTICA (Línea 44): 
    // Como 'dialog-content' era null, tomamos un hijo que SÍ existe ('text-input-container') y subimos a su elemento padre.
    const chatArea = document.getElementById('text-input-container').parentElement; 
    
    // Botones de control
    const btnYes = document.getElementById('btn-yes');
    const btnNo = document.getElementById('btn-no');
    const confirmationText = document.getElementById('confirmation-text');

    // Estado del script y datos
    let currentStep = 'name'; // 'name', 'edad', 'peso', 'genero'
    let userData = {
        nombre: '',
        edad: null,
        peso_aprox: null,
        genero: null
    };

    // NUEVO: DETECTAR ROL MAESTRO DE LA URL 
    const getRolMasterFromURL = () => {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('rol_master') || null;
    };
    const rolDeseado = getRolMasterFromURL() || 'Cliente'; 
    console.log("Rol detectado:", rolDeseado); 
    
    // Verificación de elementos críticos (Ahora la variable chatArea SIEMPRE será válida)
    if (!dialogMessage || !textInputContainer || !userInput || !confirmationContainer || !btnYes || !btnNo || !chatArea) {
        console.error("ERROR CRÍTICO: Faltan elementos esenciales en bienvenida.html para iniciar la secuencia. El script ha terminado.");
        return; 
    }

    let debounceTimer; 
    const VISIBILITY_DELAY = 4500; 
    const FADE_OUT_DELAY = 1000;
    const ATTRIBUTE_NAME = 'name'; 
    const ATTRIBUTE_WEIGHT = 'weight';

    // ------------------------------------------------------------------
    // FUNCIONES AUXILIARES: Cookie y Transiciones
    // ------------------------------------------------------------------
    const getCookie = (name) => {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null; 
    };

    const showMessage = (text, delay) => {
        return new Promise(resolve => {
            dialogMessage.textContent = text;
            dialogMessage.style.opacity = '1';
            dialogMessage.classList.add('fade-in');
            
            if (delay === 0) {
                resolve();
            } else {
                setTimeout(() => {
                    dialogMessage.style.opacity = '0';
                    setTimeout(resolve, FADE_OUT_DELAY); 
                }, delay);
            }
        });
    };

    const hideElement = (element, delay = 500) => {
        return new Promise(resolve => {
            element.style.opacity = '0';
            setTimeout(() => {
                element.style.display = 'none';
                resolve();
            }, delay);
        });
    };
    
    const showElement = (element) => {
        element.style.display = 'block';
        setTimeout(() => {
            element.style.opacity = '1';
        }, 10);
    };

    // ------------------------------------------------------------------
    // 1. SECUENCIA DE BIENVENIDA Y NOMBRE (Lógica de Persistencia)
    // ------------------------------------------------------------------

    const startWelcomeSequence = async () => {
        const deviceId = getCookie('dispositivo_id');
        if (deviceId) {
            dialogMessage.textContent = `¡Bienvenido de vuelta! Redirigiendo para verificación de rol...`;
            dialogMessage.style.opacity = '1';
            setTimeout(() => {
                window.location.href = '/'; 
            }, 1000);
            return;
        }
        
        await showMessage("Hola.", VISIBILITY_DELAY); 
        await showMessage("Soy TuC TuC. Estoy aquí para ayudarte.", 3500); 
        
        // El diálogo cambia si es Admin
        if (rolDeseado === 'Admin') {
            await showMessage("Para configurar tu cuenta de administrador, por favor, dime tu nombre.", 2000);
        } else {
            await showMessage("Por favor, dime tu nombre.", 2000); 
        }
        
        userInput.setAttribute('data-step', ATTRIBUTE_NAME);
        userInput.type = 'text';
        userInput.placeholder = 'Escribe aquí...';
        userInput.maxLength = 50;
        
        showElement(textInputContainer);
        userInput.focus();
        dialogMessage.style.opacity = '0.5'; 
        
        userInput.addEventListener('keyup', handleNameInput);
    };

    // LÓGICA CORREGIDA: Habilita Enter y Temporizador 
    const handleNameInput = (event) => {
        clearTimeout(debounceTimer);
        const currentName = userInput.value.trim();
        
        // 1. Envío Inmediato con Enter
        if (event.key === 'Enter' && currentName) {
            userInput.removeEventListener('keyup', handleNameInput); 
            showConfirmation(currentName);
            return; 
        }

        // 2. Envío por Temporizador (1 segundo después de la última pulsación)
        if (currentName) {
            debounceTimer = setTimeout(() => {
                showConfirmation(currentName);
            }, 1000); 
        } else {
            confirmationContainer.style.display = 'none';
        }
    };

    const showConfirmation = (name) => {
        hideElement(textInputContainer, 0); 
        
        confirmationText.textContent = `¿Tu nombre es "${name}"?`; 
        showElement(confirmationContainer);
        
        userData.nombre = name;
        userInput.removeEventListener('keyup', handleNameInput); 
    };

    // ------------------------------------------------------------------
    // 2. DIÁLOGO DE DATOS CONVERSACIONAL (Flujo principal después del 'Sí')
    // ------------------------------------------------------------------

    const startDataConversation = async () => {
        await hideElement(confirmationContainer);
        
        // CAMBIO CRÍTICO: SALTAR FLUJO SI ES ADMIN 
        if (rolDeseado === 'Admin') {
            await saveUserDataAndRedirect(); // Salta directamente a guardar datos
            return;
        }
        
        // FLUJO NORMAL DE CLIENTE CONTINÚA AQUÍ:
        currentStep = 'edad';
        await askAge();
    };
    
    const askAge = async () => {
        await showMessage(`${userData.nombre}, ¿en cuál de estos grupos te encuentras según tu edad?`, 500);
        showElement(ageOptionsContainer);
        
        ageOptionsContainer.querySelectorAll('.chat-btn').forEach(button => {
            button.onclick = (e) => handleAgeSelection(e.target.getAttribute('data-age-type'));
        });
    };

    const handleAgeSelection = async (ageType) => {
        await hideElement(ageOptionsContainer);
        ageOptionsContainer.querySelectorAll('.chat-btn').forEach(button => button.onclick = null); 

        if (ageType === 'SPECIFY') {
            currentStep = 'edad'; 
            await showMessage("Por favor, escribe tu edad exacta en años.", 500); 
            
            userInput.value = '';
            userInput.setAttribute('data-step', ATTRIBUTE_NAME); 
            userInput.type = 'number';
            userInput.placeholder = 'Ej: 35';
            userInput.maxLength = 3;
            
            showElement(textInputContainer);
            userInput.focus();
            userInput.addEventListener('keyup', handleSpecificAgeInput);

        } else {
            const ageMap = {
                'CHILD': 6, 'TEEN': 15, 'ADULT': 35, 'SENIOR': 75
            };
            userData.edad = ageMap[ageType];
            await askNextQuestion('peso');
        }
    };

    const handleSpecificAgeInput = (event) => {
        if (event.key === 'Enter') {
            userInput.removeEventListener('keyup', handleSpecificAgeInput);
            const age = parseInt(userInput.value.trim(), 10);
            userData.edad = isNaN(age) ? null : age;
            askNextQuestion('peso');
        }
    };


    const askNextQuestion = async (nextStep) => {
        await hideElement(textInputContainer); 
        await hideElement(dialogMessage, 0); 

        currentStep = nextStep;
        userInput.value = '';

        switch(nextStep) {
            case 'peso':
                dialogMessage.textContent = `De acuerdo, ${userData.nombre}. ¿Cuál es tu **rango de peso**? Esto ayuda con la dosificación.`;
                showElement(dialogMessage); 
                
                setTimeout(() => {
                    showElement(weightOptionsContainer); 
                }, 500);

                weightOptionsContainer.querySelectorAll('.chat-btn').forEach(button => {
                    button.onclick = (e) => handleWeightSelection(e.target.getAttribute('data-weight-range'));
                });
                break;

            case 'genero':
                dialogMessage.textContent = `${userData.nombre}, ¿cuál de estas opciones describe mejor tu género biológico?`;
                showElement(dialogMessage); 

                setTimeout(() => {
                    showElement(genderOptionsContainer);
                }, 500);

                genderOptionsContainer.querySelectorAll('.chat-btn').forEach(button => {
                    button.onclick = (e) => handleGenderSelection(e.target.getAttribute('data-gender'));
                });
                break;

            default:
                await saveUserDataAndRedirect(); 
                break;
        }
    };
    
    // Función para manejar selección de rango de peso
    const handleWeightSelection = async (weightRange) => {
        await hideElement(weightOptionsContainer);
        weightOptionsContainer.querySelectorAll('.chat-btn').forEach(button => button.onclick = null);

        if (weightRange === 'SPECIFY') {
            currentStep = 'peso'; 
            
            dialogMessage.textContent = "Por favor, escribe tu peso exacto en kilogramos (Ej: 75.5).";
            showElement(dialogMessage); 
            
            userInput.setAttribute('data-step', ATTRIBUTE_WEIGHT);
            userInput.type = 'number';
            userInput.step = '0.1';
            userInput.max = '500';
            userInput.placeholder = 'Ej: 75.5';
            
            setTimeout(() => {
                 showElement(textInputContainer);
                 userInput.focus();
            }, 500);
            
            userInput.addEventListener('keyup', handleSpecificWeightInput);
        } else {
            const weightMap = {
                'LOW': 45, 'NORMAL': 65, 'HIGH': 85, 'VERY_HIGH': 110
            };
            userData.peso_aprox = weightMap[weightRange];
            await askNextQuestion('genero');
        }
    };
    
    // Función para manejar el input de peso específico
    const handleSpecificWeightInput = (event) => {
        if (event.key === 'Enter') {
            userInput.removeEventListener('keyup', handleSpecificWeightInput);
            const weight = parseFloat(userInput.value.trim());
            userData.peso_aprox = isNaN(weight) ? null : weight;
            askNextQuestion('genero');
        }
    };


    const handleGenderSelection = async (gender) => {
        await hideElement(genderOptionsContainer);
        genderOptionsContainer.querySelectorAll('.chat-btn').forEach(button => button.onclick = null); 

        userData.genero = gender;
        await saveUserDataAndRedirect(); 
    };
    
    // ------------------------------------------------------------------
    // 3. ENVÍO FINAL DE DATOS A FLASK (Ahora con lógica de Rol)
    // ------------------------------------------------------------------

    const saveUserDataAndRedirect = async () => { 
        const finalName = userData.nombre;
        
        await hideElement(textInputContainer, 500); 
        dialogMessage.textContent = `¡Perfecto, ${finalName}! Guardando tus datos...`;
        dialogMessage.style.opacity = '1';
        
        let dispositivo_id = getCookie('dispositivo_id'); 
        if (!dispositivo_id) {
            dispositivo_id = `BACKUP_${Date.now()}`; 
            console.warn("ADVERTENCIA: No se encontró la cookie 'dispositivo_id'. Usando ID de respaldo.");
        }
        
        try {
            const dataToSend = { 
                nombre: finalName, 
                dispositivo_id: dispositivo_id,
                // Si es Admin, estos serán null.
                edad: userData.edad, 
                peso_aprox: userData.peso_aprox,
                genero: userData.genero,
                rol: rolDeseado 
            };
            console.log("Datos enviados al backend:", dataToSend);
            
            // Añadimos una verificación de si la respuesta es JSON antes de intentar parsear
            const response = await fetch('/api/finalizar_bienvenida', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dataToSend), 
            });
            
            // Si la respuesta no es OK (por ejemplo, error 500 o 400), el servidor podría devolver HTML.
            if (!response.ok) {
                const errorText = await response.text();
                console.error("Error del servidor (no JSON esperado):", errorText);
                alert(`Error al guardar datos. El servidor devolvió el código ${response.status}. Por favor, revisa los logs de Flask.`);
                window.location.reload(); 
                return;
            }

            const data = await response.json();

            if (data.status === 'success') {
                window.location.href = data.redirect_url;
            } else {
                alert(`Error al guardar datos: ${data.message}`);
                window.location.reload(); 
            }
        } catch (error) {
            console.error('Error de red o JSON al guardar los datos:', error);
            alert("Hubo un error de conexión o el servidor no respondió correctamente. Intente de nuevo.");
            window.location.reload(); 
        }
    };

    // ------------------------------------------------------------------
    // 4. EVENTOS DE CONFIRMACIÓN (Botones Sí/No)
    // ------------------------------------------------------------------

    btnYes.addEventListener('click', () => {
        startDataConversation(); 
    });

    btnNo.addEventListener('click', () => {
        hideElement(confirmationContainer);
        showElement(textInputContainer);
        userInput.value = userData.nombre; 
        userInput.focus();
        userInput.addEventListener('keyup', handleNameInput); 
    });
    
    // ------------------------------------------------------------------
    // 5. INICIO
    // ------------------------------------------------------------------

    startWelcomeSequence();
});
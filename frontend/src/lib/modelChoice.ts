export type ModelChoice = 'qwen' | 'mimo';

const STORAGE_KEY = 'lianyipei_model_choice';
const EVENT_NAME = 'lianyipei:model-choice-changed';

function normalizeModelChoice(value: string | null | undefined): ModelChoice {
  return value === 'mimo' || value === 'deepseek' ? 'mimo' : 'qwen';
}

export function getStoredModelChoice(): ModelChoice {
  try {
    return normalizeModelChoice(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return 'qwen';
  }
}

export function setStoredModelChoice(choice: ModelChoice) {
  try {
    window.localStorage.setItem(STORAGE_KEY, choice);
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: choice }));
  } catch {
    // ignore storage failures in private mode
  }
}

export function onModelChoiceChanged(callback: (choice: ModelChoice) => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) {
      callback(normalizeModelChoice(event.newValue));
    }
  };
  const onCustom = (event: Event) => {
    const customEvent = event as CustomEvent<ModelChoice>;
    callback(normalizeModelChoice(customEvent.detail));
  };

  window.addEventListener('storage', onStorage);
  window.addEventListener(EVENT_NAME, onCustom as EventListener);

  return () => {
    window.removeEventListener('storage', onStorage);
    window.removeEventListener(EVENT_NAME, onCustom as EventListener);
  };
}

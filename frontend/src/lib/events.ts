export function addCustomEventListener(
  eventName: string,
  listener: EventListener
) {
  document.addEventListener(eventName, listener);
}

export function removeCustomEventListener(
  eventName: string,
  listener: EventListener
) {
  document.removeEventListener(eventName, listener);
}

export function dispatchCustomEvent(
  eventName: string,
  data: CustomEventInit = {}
) {
  const event = new CustomEvent(eventName, { detail: data });
  document.dispatchEvent(event);
}

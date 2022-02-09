// No idea how to type this...
export function sortObj(obj: any) {
  return Object.keys(obj).sort().reduce((result: any, key: any) => {
    result[key] = obj[key];
    return result;
  }, {});
}

export function objIsEmpty(obj: any) {
  return Object.keys(obj).length === 0;
}

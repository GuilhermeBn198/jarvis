import { release as osRelease } from 'node:os';

export function isNativeLinux(env: Record<string,string|undefined> = process.env, release = osRelease(), host: string = process.platform): boolean {
  const override=env.JARVIS_PLATFORM?.trim().toLowerCase();
  if(override) {
    if(!['linux','windows','wsl'].includes(override))throw new Error('JARVIS_PLATFORM invalido');
    return override==='linux';
  }
  return host==='linux' && !/microsoft/i.test(release) && !env.WSL_INTEROP && !env.WSL_DISTRO_NAME;
}

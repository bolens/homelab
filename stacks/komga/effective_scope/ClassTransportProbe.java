/** Loaded from only the explicitly staged transport directory, never ambient classes. */
public final class ClassTransportProbe {
 public static void main(String[]args)throws Exception{
  if(args.length!=0)throw new AssertionError();
  Class<?> held=Class.forName("KomgaEffectiveScope$Held");
  var constructor=held.getDeclaredConstructor(String.class);constructor.setAccessible(true);
  Object instance=constructor.newInstance("transport-only");
  if(!(instance instanceof IllegalStateException))throw new AssertionError();
  Class<?> observation=Class.forName("TargetEffectiveScopeCase$Observation");
  if(!observation.isInterface()||observation.getDeclaredMethods().length!=1)throw new AssertionError();
  System.out.println("COMPLETE_COMPILED_TRANSPORT");
 }
}

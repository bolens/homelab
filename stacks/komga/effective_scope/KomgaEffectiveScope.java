import java.io.*;
import java.lang.reflect.*;
import java.net.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.function.Supplier;

/** Headless environment replay only. No SpringApplication/context/beans. */
public final class KomgaEffectiveScope {
 static final ClassLoader LOADER=Thread.currentThread().getContextClassLoader();
 static final Map<Path,List<Long>> FILES=new LinkedHashMap<>();
 static final Map<Path,String> HASHES=new LinkedHashMap<>();
 static final Map<Path,List<Long>> IMAGE_ABSENT=new LinkedHashMap<>();
 static final Map<Path,List<Long>> ABSENT=new LinkedHashMap<>();
 static final Map<String,String> PACKAGED=new LinkedHashMap<>();
 static final Set<String> OPENED=new HashSet<>();
 static final Map<String,byte[]> OPENED_BYTES=new HashMap<>();
 static final Map<Path,List<Long>> SCOPE_NODES=new LinkedHashMap<>();
 static final Map<Path,List<Long>> SCOPE_ABSENT=new LinkedHashMap<>();
 static List<Long> node(List<Long>n){return List.of(n.get(0),n.get(1),n.get(5),n.get(6),n.get(7));}
 static List<Path> roots;
 static Map<String,Object>host;
 static Set<String> originalPropertyNames=Set.of();
 static final Set<String> jvmPropertyNames=new HashSet<>(System.getProperties().stringPropertyNames());
 static void supportedPlaceholders(Object value){
  if(value instanceof String){String text=(String)value;need(!text.matches("(?s).*\\$\\{[^}:]*\\$\\{.*"),"dynamic-placeholder-key");
   var match=java.util.regex.Pattern.compile("\\$\\{([^{}:]+)").matcher(text);
   while(match.find()){String key=match.group(1);boolean jvm=jvmPropertyNames.contains(key)||key.matches("(?:java|javax|jdk|sun|os|user|file|path|line|native|awt)\\..*");need(!jvm||originalPropertyNames.contains(key),"uncaptured-jvm-placeholder");}
  }else if(value instanceof Map<?,?>){for(Object item:((Map<?,?>)value).values())supportedPlaceholders(item);}
  else if(value instanceof Collection<?>){for(Object item:(Collection<?>)value)supportedPlaceholders(item);}
 }
 static Object capturedResource(Object resource,byte[]raw)throws Exception{
  return java.lang.reflect.Proxy.newProxyInstance(LOADER,new Class<?>[]{type("org.springframework.core.io.Resource")},(p,m,a)->{if(m.getName().equals("getInputStream"))return new ByteArrayInputStream(raw);try{return m.invoke(resource,a);}catch(InvocationTargetException ex){throw ex.getCause();}});
 }
 static byte[] readConfig(Path p,List<Long>original)throws Exception{
  Set<String>before=KomgaClasspathMetadata.fds();try(var channel=java.nio.channels.FileChannel.open(p,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
   Path fd=KomgaClasspathMetadata.opened(before,p,original);ByteArrayOutputStream out=new ByteArrayOutputStream();var block=java.nio.ByteBuffer.allocate(8192);int count;
   while((count=channel.read(block))!=-1){need(count>0&&out.size()+count<=1048576,"config-bound");out.write(block.array(),0,count);block.clear();}
   need(KomgaClasspathMetadata.nine(fd,true).equals(original)&&KomgaClasspathMetadata.nine(p,false).equals(original),"config-read-close");return out.toByteArray();
  }
 }
 static void decodedResource(Object resource,String name,byte[]raw)throws Exception{
  String loader=name.endsWith(".properties")?"org.springframework.boot.env.PropertiesPropertySourceLoader":"org.springframework.boot.env.YamlPropertySourceLoader";
  Object instance=make(loader,new Class<?>[]{});List<?>sources=(List<?>)call(instance,"load",new Class<?>[]{String.class,type("org.springframework.core.io.Resource")},"effective-scope-decoded-census",capturedResource(resource,raw));
  for(Object source:sources)for(String key:(String[])get(source,"getPropertyNames")){supportedPlaceholders(key);supportedPlaceholders(call(source,"getProperty",new Class<?>[]{String.class},key));}
 }
 static String hostPath(Path p){Path relative=Path.of("/config").relativize(p);need(p.startsWith(Path.of("/config"))&&relative.getNameCount()<=1,"direct-normal-config-path");return relative.toString().isEmpty()?(String)host.get("host_path"):Path.of((String)host.get("host_path")).resolve(relative).toString();}
 static List<Long> numbers(Object value){need(value instanceof List,"node-list");List<Long>out=new ArrayList<>();for(Object n:(List<?>)value){need(n instanceof Number,"node-number");out.add(((Number)n).longValue());}return out;}
 static List<Long> hostNode(Path p,List<Long>child){Object raw=p.equals(Path.of("/config"))?host.get("root_identity"):((Map<?,?>)host.get("entries")).get(p.getFileName().toString());List<Long>v=raw==null?null:numbers(raw);need(v!=null&&v.size()==5&&v.subList(1,5).equals(node(child).subList(1,5)),"host-child-node-join");return v;}
 static final class Held extends IllegalStateException {final String code;Held(String code){super(code);this.code=code;}}
 static void need(boolean v,String code){if(!v)throw new Held(code);}
 static Throwable unwrap(Throwable error){for(int i=0;i<8&&(error instanceof InvocationTargetException||error instanceof UndeclaredThrowableException);i++){Throwable cause=error.getCause();if(cause==null)break;error=cause;}return error;}
 static Class<?> type(String n)throws Exception{return Class.forName(n,true,LOADER);}
 static Object call(Object o,String name,Class<?>[]types,Object...args)throws Exception{
  Class<?>c=o instanceof Class?(Class<?>)o:o.getClass();Method m=c.getMethod(name,types);Object receiver=o instanceof Class?null:o;if(!m.canAccess(receiver))m.setAccessible(true);return m.invoke(receiver,args);
 }
 static Object get(Object o,String n)throws Exception{return call(o,n,new Class<?>[]{});}
 static Object make(String n,Class<?>[]types,Object...args)throws Exception{return type(n).getConstructor(types).newInstance(args);}
 static String hash(byte[]raw)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw));}
 static boolean present(String name){try{Class.forName(name,false,LOADER);return true;}catch(ClassNotFoundException ex){return false;}}
 static void closeFiles()throws Exception{
  for(Path p:FILES.keySet())need(KomgaClasspathMetadata.nine(p,false).equals(FILES.get(p))&&hash(readConfig(p,FILES.get(p))).equals(HASHES.get(p)),"config-original-final");
  for(Path p:ABSENT.keySet())need(!Files.exists(p,LinkOption.NOFOLLOW_LINKS)&&node(KomgaClasspathMetadata.nine(p.getParent(),false)).equals(ABSENT.get(p)),"config-absence-final");
  for(Path p:IMAGE_ABSENT.keySet())need(!Files.exists(p,LinkOption.NOFOLLOW_LINKS)&&node(KomgaClasspathMetadata.nine(p.getParent(),false)).equals(IMAGE_ABSENT.get(p)),"image-config-absence-final");
  for(Path p:SCOPE_NODES.keySet())need(node(KomgaClasspathMetadata.nine(p,false)).equals(SCOPE_NODES.get(p)),"scope-node-final");
  for(Path p:SCOPE_ABSENT.keySet())need(!Files.exists(p,LinkOption.NOFOLLOW_LINKS)&&node(KomgaClasspathMetadata.nine(p.getParent(),false)).equals(SCOPE_ABSENT.get(p)),"scope-absence-final");
 }
 static boolean allowed(Path p){return roots.stream().anyMatch(p::startsWith);}
 static <T>T frameworkOutput(java.util.concurrent.Callable<T> action)throws Exception{
  PrintStream protocol=System.out;System.setOut(System.err);try{return action.call();}finally{System.setOut(protocol);}
 }
 static boolean heapOnly(String value){return value.chars().allMatch(c->c<128)&&(value.trim().isEmpty()||value.trim().matches("-Xm[sx][1-9][0-9]*[kKmMgG]?(?:[ \\t\\r\\n]+-Xm[sx][1-9][0-9]*[kKmMgG]?)*"));}
 static Path fileResourcePath(Object r,URI uri)throws Exception{
  need("file".equals(uri.getScheme()),"unsupported-resource-scheme");
  return ((File)get(r,"getFile")).toPath().toAbsolutePath().normalize();
 }
 static void resource(Object r,boolean opened)throws Exception{
  boolean exists=(Boolean)get(r,"exists");URI uri;try{uri=(URI)get(r,"getURI");}catch(InvocationTargetException ex){need(!exists&&!opened,"unresolved-existing-resource");return;}String u=uri.toString();
  if(u.startsWith("jar:file:/app/application.jar!/")){
   String name=u.substring("jar:file:/app/application.jar!/".length());if(name.isEmpty()){need(!opened,"jar-root-not-config");return;}need(name.matches("application(?:-[A-Za-z0-9_-]+)?\\.(?:yml|yaml|properties)"),"packaged-resource");
   if(opened){try(InputStream in=(InputStream)get(r,"getInputStream")){byte[]raw=in.readNBytes(1048577);need(raw.length<=1048576,"config-bound");PACKAGED.put(u,hash(raw));OPENED_BYTES.put(u,raw);decodedResource(r,name,raw);}OPENED.add(u);}return;
  }
  Path p=fileResourcePath(r,uri);
  if(Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS)){need(!opened&&Set.of(Path.of("/app"),Path.of("/checks"),Path.of("/config")).contains(p),"config-directory-anchor");return;}
  if(!allowed(p)){need(!exists&&!opened,"unreviewed-file-resource");if(Files.isDirectory(p.getParent())){List<Long>v=node(KomgaClasspathMetadata.nine(p.getParent(),false));need(IMAGE_ABSENT.putIfAbsent(p,v)==null||IMAGE_ABSENT.get(p).equals(v),"image-absence-parent-changed");}return;}
  if(p.getFileName().toString().matches("application(?:-[A-Za-z0-9_-]+)?\\.xml")){need(!exists&&!opened&&!Files.isSymbolicLink(p)&&Files.isDirectory(p.getParent()),"unsupported-existing-xml-config");List<Long>v=node(KomgaClasspathMetadata.nine(p.getParent(),false));need(ABSENT.putIfAbsent(p,v)==null||ABSENT.get(p).equals(v),"config-absent-parent-changed");return;}
  need(p.getFileName().toString().matches("application(?:-[A-Za-z0-9_-]+)?\\.(?:yml|yaml|properties)"),"unreviewed-config-name");
  if(exists){List<Long>v=KomgaClasspathMetadata.nine(p,false);need((v.get(5)&0170000)==0100000&&v.get(8)==1&&v.get(2)<=1048576,"config-file");byte[]raw=readConfig(p,v);need(FILES.putIfAbsent(p,v)==null||FILES.get(p).equals(v),"config-replaced");String sha=hash(raw);need(HASHES.putIfAbsent(p,sha)==null||HASHES.get(p).equals(sha),"config-changed");if(opened){decodedResource(r,p.getFileName().toString(),raw);OPENED_BYTES.put(u,raw);OPENED.add(u);}}
  else{need(!opened&&!Files.isSymbolicLink(p)&&Files.isDirectory(p.getParent()),"config-missing-parent");List<Long>v=node(KomgaClasspathMetadata.nine(p.getParent(),false));need(ABSENT.putIfAbsent(p,v)==null||ABSENT.get(p).equals(v),"config-absent-parent-changed");}
 }
 static void declaredLocation(String raw)throws Exception{
  String u=raw.trim().replaceFirst("^optional:","");
  if(u.startsWith("file:")){Path p=Path.of(URI.create(u)).toAbsolutePath().normalize();need(p.equals(Path.of("/config"))||(p.getParent().equals(Path.of("/config"))&&p.getFileName().toString().matches("application(?:-[A-Za-z0-9_-]+)?\\.(?:yml|yaml|properties)")),"unsupported-declared-file-location");}
  else if(u.startsWith("classpath:")){String n=u.substring("classpath:".length()).replaceFirst("^/","");need(n.isEmpty()||n.matches("application(?:-[A-Za-z0-9_-]+)?\\.(?:yml|yaml|properties)"),"unsupported-declared-classpath-location");}
  else throw new Held("unsupported-import-origin");
 }
 static Object wrapResource(Object r)throws Exception{
  Class<?>resource=type("org.springframework.core.io.Resource");
  return java.lang.reflect.Proxy.newProxyInstance(LOADER,new Class<?>[]{resource},(p,m,a)->{
   try{if(m.getName().equals("getInputStream")){resource(r,true);String uri=((URI)get(r,"getURI")).toString();need(OPENED_BYTES.containsKey(uri),"captured-config-stream");return new ByteArrayInputStream(OPENED_BYTES.get(uri));}else if(m.getName().equals("exists")||m.getName().equals("isReadable"))resource(r,false);
    Object value=m.invoke(r,a);if(value!=null&&resource.isInstance(value))return wrapResource(value);return value;
   }catch(InvocationTargetException e){throw e.getCause();}
  });
 }
 static Object resourceLoader()throws Exception{
  Object delegate=make("org.springframework.core.io.DefaultResourceLoader",new Class<?>[]{ClassLoader.class},LOADER);Class<?>kind=type("org.springframework.core.io.ResourceLoader");
  return java.lang.reflect.Proxy.newProxyInstance(LOADER,new Class<?>[]{kind},(p,m,a)->{try{Object v=m.invoke(delegate,a);return m.getName().equals("getResource")?wrapResource(v):v;}catch(InvocationTargetException e){throw e.getCause();}});
 }
 static Object deferredLog()throws Exception{
  Object noop=make("org.apache.commons.logging.impl.NoOpLog",new Class<?>[]{});Class<?>kind=type("org.springframework.boot.logging.DeferredLogFactory");
  return java.lang.reflect.Proxy.newProxyInstance(LOADER,new Class<?>[]{kind},(p,m,a)->noop);
 }
 static void processor(String name,Object env,Object logs)throws Exception{
  Class<?>c=type(name),envType=type("org.springframework.core.env.ConfigurableEnvironment"),app=type("org.springframework.boot.SpringApplication");Object instance;
  try{Constructor<?>ctor=c.getDeclaredConstructor();ctor.setAccessible(true);instance=ctor.newInstance();}catch(NoSuchMethodException ex){Constructor<?>ctor=c.getDeclaredConstructor(type("org.springframework.boot.logging.DeferredLogFactory"));ctor.setAccessible(true);instance=ctor.newInstance(logs);}
  Method m=c.getMethod("postProcessEnvironment",envType,app);m.setAccessible(true);m.invoke(instance,env,null);
 }
 static Map<String,Object> collect(Map<String,Object>input)throws Exception{return frameworkOutput(()->collectEnvironment(input));}
 static Map<String,Object> collectEnvironment(Map<String,Object>input)throws Exception{
  need(input.keySet().equals(Set.of("version","kind","properties","environment","args","config_roots","source_sha256","runtime_sha256","image","container_id","pid","start_time","mount"))&&input.get("version") instanceof Number&&((Number)input.get("version")).longValue()==1&&"original-komga-effective-input-v1".equals(input.get("kind")),"input-schema");
  host=(Map<String,Object>)input.get("mount");need(host.keySet().equals(Set.of("host_path","root_identity","entries","config_files"))&&Path.of((String)host.get("host_path")).isAbsolute(),"host-input");
  Map<String,Object>props=new LinkedHashMap<>((Map<String,Object>)input.get("properties")),environment=(Map<String,Object>)input.get("environment");List<String>args=(List<String>)input.get("args");roots=new ArrayList<>();
  need(props.size()<=256&&environment.size()<=512&&args.size()<=128,"input-bound");for(Map<String,Object>map:List.of(props,environment))for(var e:map.entrySet())need(e.getKey().length()<=256&&e.getValue() instanceof String&&((String)e.getValue()).length()<=65536,"input-value");
  for(String s:(List<String>)input.get("config_roots")){Path p=Path.of(s);need(p.isAbsolute()&&p.normalize().equals(p)&&Files.isDirectory(p)&&!Files.isSymbolicLink(p),"config-root");roots.add(p);}need(roots.size()==1&&roots.get(0).equals(Path.of("/config")),"normal-config-contract");
  need(Objects.equals(props.get("user.dir"),System.getProperty("user.dir")),"observer-workdir");for(String key:List.of("JAVA_TOOL_OPTIONS","JDK_JAVA_OPTIONS","_JAVA_OPTIONS"))if(environment.containsKey(key))need(heapOnly((String)environment.get(key)),"unsupported-agent-input");
  need(!present("reactor.tools.agent.ReactorDebugAgent")&&!present("io.micrometer.tracing.Tracer"),"unsupported-runtime-extension");need(LOADER.getResource("META-INF/spring.integration.properties")==null,"integration-resource-not-captured");
  Map<String,Object>application=KomgaClasspathMetadata.readJar(Path.of("/app/application.jar"),true);
  Object env=make("org.springframework.core.env.StandardEnvironment",new Class<?>[]{}),sources=get(env,"getPropertySources");Class<?>ps=type("org.springframework.core.env.PropertySource"),environmentType=type("org.springframework.core.env.Environment"),configurable=type("org.springframework.core.env.ConfigurableEnvironment");
  call(sources,"remove",new Class<?>[]{String.class},"systemProperties");call(sources,"remove",new Class<?>[]{String.class},"systemEnvironment");props.put("org.jooq.no-logo","true");props.put("org.jooq.no-tips","true");originalPropertyNames=new HashSet<>(props.keySet());supportedPlaceholders(props);supportedPlaceholders(environment);for(String arg:args)supportedPlaceholders(arg);
  call(sources,"addLast",new Class<?>[]{ps},make("org.springframework.core.env.MapPropertySource",new Class<?>[]{String.class,Map.class},"systemProperties",props));call(sources,"addLast",new Class<?>[]{ps},make("org.springframework.core.env.SystemEnvironmentPropertySource",new Class<?>[]{String.class,Map.class},"systemEnvironment",environment));
  if(!args.isEmpty())call(sources,"addFirst",new Class<?>[]{ps},make("org.springframework.core.env.SimpleCommandLinePropertySource",new Class<?>[]{String[].class},(Object)args.toArray(String[]::new)));
  call(type("org.springframework.boot.context.properties.source.ConfigurationPropertySources"),"attach",new Class<?>[]{environmentType},env);Object logs=deferredLog();
  processor("org.springframework.boot.env.RandomValuePropertySourceEnvironmentPostProcessor",env,logs);
  // The original Application sets no environment prefix. Base systemEnvironment
  // resolves exactly the same values as Boot's origin-only wrapper; no null app.
  // Equal order HIGHEST+5: preserve actual spring.factories stable VCAP-before-JSON order.
  processor("org.springframework.boot.cloud.CloudFoundryVcapEnvironmentPostProcessor",env,logs);processor("org.springframework.boot.env.SpringApplicationJsonEnvironmentPostProcessor",env,logs);
  Class<?>cde=type("org.springframework.boot.context.config.ConfigDataEnvironmentPostProcessor");Object bootstrap=make("org.springframework.boot.DefaultBootstrapContext",new Class<?>[]{}),post=cde.getConstructor(type("org.springframework.boot.logging.DeferredLogFactory"),type("org.springframework.boot.ConfigurableBootstrapContext")).newInstance(logs,bootstrap);
  // Exact3.5.16 overload used by applyTo; avoids constructing SpringApplication
  // or creating a real logging backend. Reflection is limited to this method.
  Method apply=cde.getDeclaredMethod("postProcessEnvironment",configurable,type("org.springframework.core.io.ResourceLoader"),Collection.class);apply.setAccessible(true);apply.invoke(post,env,resourceLoader(),List.of());
  processor("org.springframework.boot.reactor.ReactorEnvironmentPostProcessor",env,logs);
  if("true".equals(System.getProperty("reactor.schedulers.defaultBoundedElasticOnVirtualThreads")))props.put("reactor.schedulers.defaultBoundedElasticOnVirtualThreads","true");
  Class<?>enumerable=type("org.springframework.core.env.EnumerablePropertySource");List<String>sourceClasses=new ArrayList<>();int names=0;
  for(Object source:(Iterable<?>)sources){String name=(String)get(source,"getName"),klass=source.getClass().getName();sourceClasses.add(klass);
   if(!enumerable.isInstance(source)){need(Set.of("org.springframework.boot.context.properties.source.ConfigurationPropertySourcesPropertySource","org.springframework.boot.env.RandomValuePropertySource").contains(klass),"non-enumerable-source");continue;}
   for(String key:(String[])get(source,"getPropertyNames")){need(++names<=20000,"property-census-bound");Object raw=call(source,"getProperty",new Class<?>[]{String.class},key);supportedPlaceholders(key);supportedPlaceholders(raw);if(raw instanceof String){String str=(String)raw;need(!str.contains("${random."),"unreplayable-random-input");if(Set.of("springconfigimport","springconfiglocation","springconfigadditionallocation").contains(key.replaceAll("[^A-Za-z]","").toLowerCase(Locale.ROOT))){String resolved=(String)call(env,"resolveRequiredPlaceholders",new Class<?>[]{String.class},str);for(String location:resolved.split("[,;]"))declaredLocation(location);}}
    Object origin=call(type("org.springframework.boot.origin.OriginLookup"),"getOrigin",new Class<?>[]{Object.class,Object.class},source,key);
    if(origin!=null&&origin.getClass().getName().equals("org.springframework.boot.origin.TextResourceOrigin")){Object r=get(origin,"getResource");String uri=((URI)get(r,"getURI")).toString();need(OPENED.contains(uri),"unclosed-config-origin");}
   }
   need(!klass.contains("ConfigTree")&&!name.startsWith("env:")&&!klass.contains("ConfigDataEnvironmentContributors"),"unsupported-property-origin");
  }
  Object binder=call(type("org.springframework.boot.context.properties.bind.Binder"),"get",new Class<?>[]{environmentType},env),bound=call(binder,"bind",new Class<?>[]{String.class,Class.class},"komga",type("org.gotson.komga.infrastructure.configuration.KomgaProperties")),komga=get(bound,"get");
  Map<String,Object>scopes=new LinkedHashMap<>();scopes.put("config",get(komga,"getConfigDir"));scopes.put("database",get(get(komga,"getDatabase"),"getFile"));scopes.put("tasks",get(get(komga,"getTasksDb"),"getFile"));scopes.put("index",get(get(komga,"getLucene"),"getDataDirectory"));scopes.put("fonts",get(get(komga,"getFonts"),"getDataDirectory"));
  Map<String,Object>scopeValues=new LinkedHashMap<>(),presence=new LinkedHashMap<>(),identities=new LinkedHashMap<>(),optional=new LinkedHashMap<>();
  for(var e:scopes.entrySet()){need(e.getValue() instanceof String,"scope-value");Path path=Path.of((String)e.getValue()).toAbsolutePath().normalize();need(allowed(path)&&!Files.isSymbolicLink(path),"scope-root");scopeValues.put(e.getKey(),Map.of("host_path",hostPath(path)));boolean exists=Files.exists(path,LinkOption.NOFOLLOW_LINKS);presence.put(e.getKey(),exists);if(exists){List<Long>n=KomgaClasspathMetadata.nine(path,false);SCOPE_NODES.put(path,node(n));identities.put(hostPath(path),hostNode(path,n));}else{need(e.getKey().equals("fonts")&&Files.isDirectory(path.getParent()),"required-scope-missing");List<Long>n=KomgaClasspathMetadata.nine(path.getParent(),false);SCOPE_ABSENT.put(path,node(n));need(!((Map<?,?>)host.get("entries")).containsKey(path.getFileName().toString()),"host-fonts-absence");optional.put(hostPath(path),Map.of("nearest_existing_ancestor",hostPath(path.getParent()),"ancestor_identity",hostNode(path.getParent(),n)));}}
  closeFiles();Map<String,Object>configFiles=new LinkedHashMap<>();for(Path p:FILES.keySet()){Map<?,?>original=(Map<?,?>)((Map<?,?>)host.get("config_files")).get(p.toString());need(original!=null&&HASHES.get(p).equals(original.get("sha256")),"original-host-config-hash");configFiles.put(hostPath(p),Map.of("sha256",HASHES.get(p),"signature9",original.get("signature9")));}
  Map<String,Object>out=new LinkedHashMap<>();out.put("kind","komga-effective-persistent-scope-observation");for(String key:List.of("source_sha256","runtime_sha256","image","container_id","pid","start_time"))out.put(key,input.get(key));out.put("jar_sha256",application.get("sha256"));out.put("source_commit",KomgaClasspathMetadata.COMMIT);out.put("scopes",scopeValues);out.put("scope_presence",presence);out.put("scope_identities",identities);out.put("optional_absent_scopes",optional);out.put("config_files",configFiles);out.put("absent_config_files",ABSENT.keySet().stream().map(KomgaEffectiveScope::hostPath).toList());out.put("packaged_resources",PACKAGED);out.put("property_source_classes",sourceClasses);out.put("scope_observation_verified",false);out.put("final_ack_required",true);out.put("unsupported_imports_observed",false);out.put("all_library_settings_verified",false);out.put("process_verified_by_parent",false);out.put("application_context_started",false);return out;
 }
 public static void main(String[]args){try{
  need(args.length==0,"no-arguments");BufferedReader in=new BufferedReader(new InputStreamReader(System.in,java.nio.charset.StandardCharsets.UTF_8));String line=in.readLine();need(line!=null&&line.length()<=524288,"input-bound");Map<String,Object>input=frameworkOutput(()->{Object parser=call(type("org.springframework.boot.json.JsonParserFactory"),"getJsonParser",new Class<?>[]{});return(Map<String,Object>)call(parser,"parseMap",new Class<?>[]{String.class},line);});String report=KomgaClasspathMetadata.json(collect(input));need(report.length()<=1048576,"report-bound");String sha=hash(report.getBytes(java.nio.charset.StandardCharsets.UTF_8));System.out.println("SCOPE_READY "+Base64.getEncoder().encodeToString(report.getBytes(java.nio.charset.StandardCharsets.UTF_8)));System.out.flush();need(("ACCEPT "+sha).equals(in.readLine()),"original-parent-ack");closeFiles();System.out.println("SCOPE_ACK "+sha);System.out.flush();
 }catch(Throwable e){Throwable cause=unwrap(e);System.err.println("effective-scope-held:"+(cause instanceof Held?((Held)cause).code:"framework-refused"));System.exit(2);}}
}
